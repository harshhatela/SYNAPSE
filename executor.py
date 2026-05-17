import json
import logging
from langgraph.prebuilt import create_react_agent

from agent_prompts import build_prompt
from tool_schemas import Plan, PlanStep, StepResult

logger = logging.getLogger("synapse.executor")

MAX_REPLANS = 2


class Executor:
    """Runs a Plan step-by-step with retry-then-replan failure handling.

    Each step is executed via a fresh ReAct sub-call against the full tool
    registry; the plan and previous step summaries are injected into the
    step prompt so the agent can use them as context.
    """

    def __init__(self, llm, tools, memory, sio, sid, planner):
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.sio = sio
        self.sid = sid
        self.planner = planner
        self._replans_used = 0

    async def _emit_status(self, step_id: int, status: str, message: str = ""):
        await self.sio.emit(
            "step_status",
            {"step_id": step_id, "status": status, "message": message},
            to=self.sid,
        )

    def _build_step_prompt(self, plan: Plan, current: PlanStep,
                           prior_results: list[StepResult]) -> str:
        plan_lines = []
        done_ids = {r.step_id: r for r in prior_results}
        for s in plan.steps:
            if s.step_id < current.step_id:
                r = done_ids.get(s.step_id)
                tag = "✓" if (r and r.status == "done") else "✗"
                plan_lines.append(f"  {tag} step {s.step_id}: {s.description}")
            elif s.step_id == current.step_id:
                plan_lines.append(f"  → step {s.step_id}: {s.description}")
            else:
                plan_lines.append(f"    step {s.step_id}: {s.description}")
        prev = "\n".join(
            f"step {r.step_id}: {r.summary}" for r in prior_results
        ) or "(none)"
        return (
            f"We are executing a plan.\n"
            f"Plan:\n" + "\n".join(plan_lines) + "\n\n"
            f"Previous step summaries:\n{prev}\n\n"
            f"CURRENT STEP {current.step_id}: {current.description}\n"
            f"Success criteria: {current.success_criteria}\n"
            f"Intended tool: {current.intended_tool}\n\n"
            f"Execute this step now. Use the intended tool unless you have a strong reason "
            f"not to. End your reply with a single line: SUMMARY: <one sentence>."
        )

    async def _run_react_step(self, prompt: str) -> tuple[str, str, list[dict]]:
        """Returns (status, summary, tool_outputs).

        status is "done" if all tool calls report success (or none ran),
        else "failed".
        """
        agent = create_react_agent(self.llm, self.tools, state_modifier=build_prompt(""))
        final_text_parts: list[str] = []
        tool_outputs: list[dict] = []
        any_tool_fail = False

        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": prompt}]}, version="v2"
        ):
            kind = event.get("event")
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    final_text_parts.append(chunk.content)
                    await self.sio.emit("token", {"data": chunk.content}, to=self.sid)
            elif kind == "on_tool_start":
                await self.sio.emit("tool_call", {
                    "tool": event["name"], "status": "running",
                    "input": str(event["data"].get("input", {}))[:200],
                }, to=self.sid)
            elif kind == "on_tool_end":
                output = str(event["data"].get("output", ""))
                tool_outputs.append({"tool": event["name"], "output": output[:500]})
                if self._tool_output_signals_failure(output):
                    any_tool_fail = True
                await self.sio.emit("tool_call", {
                    "tool": event["name"], "status": "done",
                    "output": output[:200],
                }, to=self.sid)

        final_text = "".join(final_text_parts)
        summary = self._extract_summary(final_text)
        status = "failed" if any_tool_fail else "done"
        return status, summary, tool_outputs

    @staticmethod
    def _extract_summary(text: str) -> str:
        for line in reversed(text.splitlines()):
            if line.strip().lower().startswith("summary:"):
                return line.split(":", 1)[1].strip()
        return (text.strip()[:200] or "(no summary)")

    @staticmethod
    def _tool_output_signals_failure(output: str) -> bool:
        """Tools serialize Pydantic models to JSON; success is the source of truth."""
        try:
            data = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            return False
        return data.get("success") is False if isinstance(data, dict) else False

    async def run_plan(self, plan: Plan, session_id: str) -> list[StepResult]:
        results: list[StepResult] = []
        current_plan = plan
        i = 0
        while i < len(current_plan.steps):
            step = current_plan.steps[i]
            done_ids = {r.step_id for r in results if r.status == "done"}
            if step.step_id in done_ids:
                # Replan may include a step_id we already completed. Skip it.
                i += 1
                continue
            await self._emit_status(step.step_id, "running")

            status, summary, outs = await self._run_react_step(
                self._build_step_prompt(current_plan, step, results)
            )
            if status == "done":
                await self._emit_status(step.step_id, "done", summary)
                results.append(StepResult(
                    step_id=step.step_id, status="done",
                    summary=summary, tool_outputs=outs,
                ))
                i += 1
                continue

            # retry once
            await self._emit_status(step.step_id, "retry", "first attempt failed")
            status, summary, outs = await self._run_react_step(
                self._build_step_prompt(current_plan, step, results)
            )
            if status == "done":
                await self._emit_status(step.step_id, "done", summary)
                results.append(StepResult(
                    step_id=step.step_id, status="done",
                    summary=summary, tool_outputs=outs,
                ))
                i += 1
                continue

            # replan
            await self._emit_status(step.step_id, "failed", summary)
            results.append(StepResult(
                step_id=step.step_id, status="failed",
                summary=summary, tool_outputs=outs,
            ))
            if self._replans_used >= MAX_REPLANS:
                logger.warning("Executor: replan cap reached, halting")
                break
            new_plan = self.planner.replan(
                original=current_plan,
                completed_step_ids=[r.step_id for r in results if r.status == "done"],
                failure_context=f"step {step.step_id} failed: {summary}",
            )
            self._replans_used += 1
            if not new_plan or not new_plan.steps:
                logger.warning("Executor: replan returned empty, halting")
                break
            await self.sio.emit(
                "plan_generated",
                {"plan": new_plan.model_dump(), "replanned": True},
                to=self.sid,
            )
            current_plan = new_plan
            i = 0  # execute the new plan from the start
        return results
