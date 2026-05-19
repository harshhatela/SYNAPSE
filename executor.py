import json
import logging
import re
from langgraph.prebuilt import create_react_agent

from agent_prompts import build_prompt
from model_router import is_rate_limit_error
from tool_schemas import Plan, PlanStep, StepResult

logger = logging.getLogger("synapse.executor")

MAX_REPLANS = 2


class Executor:
    """Runs a Plan step-by-step with retry-then-replan failure handling.

    Each step is executed via a fresh ReAct sub-call against the full tool
    registry; the plan and previous step summaries are injected into the
    step prompt so the agent can use them as context.
    """

    def __init__(self, router, tools, memory, sio, sid, planner, request_id: str = None):
        self.router = router
        self.tools = tools
        self.memory = memory
        self.sio = sio
        self.sid = sid
        self.planner = planner
        self.request_id = request_id
        self.final_plan: Plan | None = None
        self._replans_used = 0

    def _payload(self, **data):
        if self.request_id:
            data["request_id"] = self.request_id
        return data

    async def _emit_status(self, step_id: int, status: str, message: str = ""):
        await self.sio.emit(
            "step_status",
            self._payload(step_id=step_id, status=status, message=message),
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

        summaries = "\n".join(
            f"step {r.step_id}: {r.summary}" for r in prior_results
        ) or "(none)"

        # Include raw tool outputs from recent prior steps so this step can quote
        # container IDs, run IDs, file paths, etc. verbatim instead of re-deriving
        # them with brittle shell substitutions.
        output_lines: list[str] = []
        for r in prior_results[-3:]:
            for t in r.tool_outputs:
                snippet = (t.get("output") or "").strip().replace("\n", " ")[:400]
                output_lines.append(f"  [step {r.step_id} · {t.get('tool')}]: {snippet}")
        outputs_block = "\n".join(output_lines) or "(none)"

        return (
            "We are executing a plan.\n"
            "Plan:\n" + "\n".join(plan_lines) + "\n\n"
            f"Previous step summaries:\n{summaries}\n\n"
            f"Recent tool outputs (use these values literally — do NOT use $(...) "
            f"shell substitution):\n{outputs_block}\n\n"
            f"CURRENT STEP {current.step_id}: {current.description}\n"
            f"Success criteria: {current.success_criteria}\n"
            f"Intended tool: {current.intended_tool}\n\n"
            "Execute this step now. Use the intended tool unless you have a strong reason "
            "not to. End your reply with a single line:\n"
            "SUMMARY: <one sentence — include any container IDs / names / file paths / "
            "run_ids that a later step might need>."
        )

    async def _run_react_step(self, prompt: str) -> tuple[str, str, list[dict]]:
        """Returns (status, summary, tool_outputs).

        Tries each configured LLM provider in order; on a rate-limit error,
        moves on to the next provider and starts the step over (the previous
        attempt produced no partial state because the request was rejected
        before streaming began).
        """
        clients = self.router.get_clients_ordered()
        if not clients:
            raise RuntimeError("Executor: no LLM clients available")

        last_exc: BaseException | None = None
        for provider, client in clients:
            try:
                if hasattr(self.router, "mark_current"):
                    self.router.mark_current(provider)
                await self.sio.emit(
                    "provider_update",
                    self._payload(provider=provider, status="active"),
                    to=self.sid,
                )
                return await self._run_one_attempt(client, prompt)
            except Exception as exc:
                if is_rate_limit_error(exc):
                    logger.warning(
                        "Executor: %s rate-limited (%s); failing over",
                        provider, str(exc)[:120],
                    )
                    await self.sio.emit(
                        "provider_update",
                        self._payload(provider=provider, status="rate_limited"),
                        to=self.sid,
                    )
                    last_exc = exc
                    continue
                raise
        raise RuntimeError(
            f"Executor: all providers rate-limited. Last error: {last_exc}"
        )

    async def _run_one_attempt(self, client, prompt: str) -> tuple[str, str, list[dict]]:
        agent = create_react_agent(client, self.tools, state_modifier=build_prompt(""))
        final_text_parts: list[str] = []
        tool_outputs: list[dict] = []
        any_tool_fail = False
        intended_tool = self._extract_intended_tool(prompt)

        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": prompt}]}, version="v2"
        ):
            kind = event.get("event")
            if kind == "on_chat_model_start":
                # Reset on each LLM turn; we only want the final answer for SUMMARY extraction.
                final_text_parts = []
            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    final_text_parts.append(chunk.content)
                    await self.sio.emit(
                        "token",
                        self._payload(data=chunk.content, scope="step"),
                        to=self.sid,
                    )
            elif kind == "on_tool_start":
                await self.sio.emit("tool_call", {
                    "tool": event["name"], "status": "running",
                    "input": str(event["data"].get("input", {}))[:200],
                    **({"request_id": self.request_id} if self.request_id else {}),
                }, to=self.sid)
            elif kind == "on_tool_end":
                output = self._extract_tool_output(event["data"].get("output", ""))
                tool_outputs.append({"tool": event["name"], "output": output[:500]})
                if self._tool_output_signals_failure(output):
                    any_tool_fail = True
                await self.sio.emit("tool_call", {
                    "tool": event["name"], "status": "done",
                    "output": output[:200],
                    **({"request_id": self.request_id} if self.request_id else {}),
                }, to=self.sid)

        final_text = "".join(final_text_parts)
        summary = self._extract_summary(final_text)
        if any_tool_fail:
            status = "failed"
        elif intended_tool == "reasoning":
            status = "done" if summary != "(no summary)" else "failed"
        elif not tool_outputs:
            status = "failed"
            summary = f"Expected tool {intended_tool or '(unknown)'} was not called"
        elif intended_tool and intended_tool not in {t["tool"] for t in tool_outputs}:
            status = "failed"
            summary = f"Expected tool {intended_tool} was not called"
        else:
            status = "done"
        return status, summary, tool_outputs

    @staticmethod
    def _extract_intended_tool(prompt: str) -> str | None:
        match = re.search(r"^Intended tool:\s*(.+)$", prompt, flags=re.MULTILINE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_summary(text: str) -> str:
        cleaned = Executor._strip_tool_call_leakage(text)
        for line in reversed(cleaned.splitlines()):
            if line.strip().lower().startswith("summary:"):
                return line.split(":", 1)[1].strip()
        return (cleaned.strip()[:200] or "(no summary)")

    @staticmethod
    def _strip_tool_call_leakage(text: str) -> str:
        """Some local models emit the tool-call protocol as prose instead of
        through the structured tool_calls API. Strip those markers so the
        leaked text doesn't pollute summaries or plan descriptions."""
        import re
        # Patterns observed: "[TOOL_CALLS]", "**Calling function "name"**",
        # bare {"command": "..."} blocks left dangling after a leaked call.
        patterns = [
            r"\[TOOL_CALLS\]",
            r"\*\*Calling function [^*]+\*\*",
            r'^\s*\{"command":[^}]+\}\s*$',
        ]
        out = text
        for p in patterns:
            out = re.sub(p, "", out, flags=re.MULTILINE)
        return out

    @staticmethod
    def _extract_tool_output(raw) -> str:
        """Normalize tool output across langchain/langgraph shapes.

        langgraph's ToolNode wraps results in ToolMessage(content=...); older
        callbacks pass the raw string. Either way we want the JSON payload
        the tool actually returned, not a stringified wrapper.
        """
        if raw is None:
            return ""
        if isinstance(raw, str):
            return raw
        content = getattr(raw, "content", None)
        if isinstance(content, str):
            return content
        return str(raw)

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
        self.final_plan = current_plan
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
                self._payload(plan=new_plan.model_dump(), replanned=True),
                to=self.sid,
            )
            current_plan = new_plan
            self.final_plan = current_plan
            i = 0  # execute the new plan from the start
        self.final_plan = current_plan
        return results
