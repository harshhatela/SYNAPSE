# SYNAPSE v3 Implementation Plan — Planner/Executor, Local Docker+K8s, Mission-Control UI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reliable multi-step task orchestration (planner+executor with retry+replan), switch Docker and kubectl to local-host execution, and redesign the frontend into a two-pane mission-control layout.

**Architecture:** Triage every user prompt — trivial ones run the existing single ReAct call; multi-step prompts go through Planner → Executor. Planner emits a JSON plan, Executor runs each step as a focused ReAct sub-call against the existing tool registry, with one retry and at most two replans on failure. Docker and kubectl tools shell out to local subprocesses; SSH/RHEL stays for the Linux shell tool only. UI renders a live plan panel beside the chat stream.

**Tech Stack:** Python 3.11, FastAPI, Socket.IO, LangGraph, LangChain, Pydantic v2, pytest, paramiko (existing), subprocess (new), Vite + React + TypeScript + TailwindCSS.

**Spec:** `docs/superpowers/specs/2026-05-17-synapse-v3-planner-design.md`

---

## Task 1: Add new Pydantic schemas

**Files:**
- Modify: `tool_schemas.py` (append after existing models)

- [ ] **Step 1: Append new schemas to `tool_schemas.py`**

```python
# ─── Kubernetes ──────────────────────────────────────────

class KubectlCommandInput(BaseModel):
    command: str  # kubectl arguments, e.g. "get pods", "apply -f deploy.yml"

class KubectlOutput(ToolOutput):
    tool_name: str = "kubectl"
    stdout: str
    stderr: Optional[str] = None
    exit_code: int

# ─── Planner / Executor ─────────────────────────────────

class PlanStep(BaseModel):
    step_id: int
    description: str          # 1-sentence, human-readable
    intended_tool: str        # tool name from registry, or "reasoning"
    success_criteria: str     # 1-sentence success condition

class Plan(BaseModel):
    steps: list[PlanStep]
    reasoning: str            # 1-3 sentences

class StepResult(BaseModel):
    step_id: int
    status: Literal["done", "failed"]
    summary: str
    tool_outputs: list[dict] = []
```

- [ ] **Step 2: Verify the file still imports cleanly**

Run: `python -c "import tool_schemas; print(tool_schemas.Plan.model_fields)"`
Expected: prints field info for `Plan` model, no error.

- [ ] **Step 3: Commit**

```bash
git add tool_schemas.py
git commit -m "feat(schemas): add Kubectl, Plan, PlanStep, StepResult models"
```

---

## Task 2: Local Docker agent (rewrite)

**Files:**
- Modify: `docker_agent.py` (full rewrite)
- Test: `tests/test_local_docker.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_local_docker.py`:

```python
import json
from unittest.mock import patch, MagicMock
import subprocess
import pytest
from docker_agent import LocalDockerAgent


def _fake_completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    cp = MagicMock()
    cp.stdout = stdout
    cp.stderr = stderr
    cp.returncode = returncode
    return cp


def test_run_command_success():
    agent = LocalDockerAgent()
    with patch("docker_agent.subprocess.run", return_value=_fake_completed(stdout="hello\n")):
        out = json.loads(agent.run_command("ps"))
    assert out["success"] is True
    assert out["stdout"] == "hello"
    assert out["exit_code"] == 0


def test_run_command_nonzero_exit():
    agent = LocalDockerAgent()
    with patch("docker_agent.subprocess.run",
               return_value=_fake_completed(stderr="boom", returncode=1)):
        out = json.loads(agent.run_command("foo"))
    assert out["success"] is False
    assert "boom" in (out.get("stderr") or "")
    assert out["exit_code"] == 1


def test_run_command_timeout():
    agent = LocalDockerAgent(timeout=1)
    with patch("docker_agent.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="docker ps", timeout=1)):
        out = json.loads(agent.run_command("ps"))
    assert out["success"] is False
    assert "timed out" in out["summary"].lower()


def test_run_command_docker_not_found():
    agent = LocalDockerAgent()
    with patch("docker_agent.subprocess.run",
               side_effect=FileNotFoundError("docker not on PATH")):
        out = json.loads(agent.run_command("ps"))
    assert out["success"] is False
    assert "docker" in out["summary"].lower()
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_local_docker.py -v`
Expected: 4 failures — `LocalDockerAgent` not defined.

- [ ] **Step 3: Replace `docker_agent.py` with the local subprocess implementation**

```python
import json
import shlex
import logging
import subprocess
import sys
from typing import Optional

from tool_schemas import DockerOutput

logger = logging.getLogger(__name__)


class LocalDockerAgent:
    """Runs `docker <command>` on the local host via subprocess.

    Docker Desktop (or `docker` on PATH) must be installed and running.
    No SSH involved — host-local only.
    """

    def __init__(self, timeout: int = 120):
        self.timeout = timeout
        self._detect_logged = False

    def detect(self) -> Optional[str]:
        """Returns None if docker is available, else an error string."""
        try:
            cp = subprocess.run(
                ["docker", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if cp.returncode != 0:
                return f"docker --version exited {cp.returncode}: {cp.stderr.strip()}"
            return None
        except FileNotFoundError:
            return "docker binary not found on PATH (install Docker Desktop)"
        except Exception as e:
            return f"docker detect failed: {e}"

    def run_command(self, command: str) -> str:
        """Run `docker <command>` locally. Returns JSON-serialized DockerOutput."""
        argv = ["docker", *shlex.split(command, posix=(sys.platform != "win32"))]
        try:
            cp = subprocess.run(
                argv, capture_output=True, text=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return DockerOutput(
                success=False,
                summary=f"docker {command}: timed out after {self.timeout}s",
                error="timeout",
            ).model_dump_json()
        except FileNotFoundError:
            return DockerOutput(
                success=False,
                summary="docker binary not found on PATH (install Docker Desktop)",
                error="not_found",
            ).model_dump_json()
        except Exception as e:
            return DockerOutput(
                success=False,
                summary=f"docker {command}: {e}",
                error=str(e),
            ).model_dump_json()

        stdout = (cp.stdout or "").strip()
        stderr = (cp.stderr or "").strip()
        ok = cp.returncode == 0
        payload = DockerOutput(
            success=ok,
            summary=(f"docker {command}: ok" if ok
                     else f"docker {command}: exit {cp.returncode}"),
            error=None if ok else stderr,
        ).model_dump()
        payload["stdout"] = stdout
        payload["stderr"] = stderr
        payload["exit_code"] = cp.returncode
        return json.dumps(payload)
```

- [ ] **Step 4: Run tests, expect pass**

Run: `pytest tests/test_local_docker.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add docker_agent.py tests/test_local_docker.py
git commit -m "feat(docker): replace SSH-routed DockerTool with LocalDockerAgent (host subprocess)"
```

---

## Task 3: Local kubectl agent

**Files:**
- Create: `kubectl_agent.py`
- Test: `tests/test_kubectl.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_kubectl.py`:

```python
import json
import subprocess
from unittest.mock import patch, MagicMock
from kubectl_agent import LocalKubectlAgent


def _cp(stdout="", stderr="", rc=0):
    m = MagicMock()
    m.stdout = stdout; m.stderr = stderr; m.returncode = rc
    return m


def test_kubectl_success():
    a = LocalKubectlAgent()
    with patch("kubectl_agent.subprocess.run", return_value=_cp(stdout="pods\n")):
        out = json.loads(a.run_command("get pods"))
    assert out["success"] is True
    assert out["stdout"] == "pods"


def test_kubectl_nonzero():
    a = LocalKubectlAgent()
    with patch("kubectl_agent.subprocess.run", return_value=_cp(stderr="nope", rc=1)):
        out = json.loads(a.run_command("apply -f bad.yml"))
    assert out["success"] is False
    assert out["exit_code"] == 1


def test_kubectl_timeout():
    a = LocalKubectlAgent(timeout=1)
    with patch("kubectl_agent.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="kubectl", timeout=1)):
        out = json.loads(a.run_command("get pods"))
    assert out["success"] is False
    assert "timed out" in out["summary"].lower()


def test_kubectl_not_found():
    a = LocalKubectlAgent()
    with patch("kubectl_agent.subprocess.run", side_effect=FileNotFoundError()):
        out = json.loads(a.run_command("get pods"))
    assert out["success"] is False
    assert "kubectl" in out["summary"].lower()
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_kubectl.py -v`
Expected: 4 failures — `kubectl_agent` not importable.

- [ ] **Step 3: Implement `kubectl_agent.py`**

```python
import json
import shlex
import sys
import logging
import subprocess
from typing import Optional

from tool_schemas import KubectlOutput

logger = logging.getLogger(__name__)


class LocalKubectlAgent:
    """Runs `kubectl <command>` on the local host via subprocess."""

    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def detect(self) -> Optional[str]:
        try:
            cp = subprocess.run(
                ["kubectl", "version", "--client", "--output=yaml"],
                capture_output=True, text=True, timeout=5,
            )
            if cp.returncode != 0:
                return f"kubectl client version exited {cp.returncode}"
            return None
        except FileNotFoundError:
            return "kubectl binary not found on PATH"
        except Exception as e:
            return f"kubectl detect failed: {e}"

    def run_command(self, command: str) -> str:
        argv = ["kubectl", *shlex.split(command, posix=(sys.platform != "win32"))]
        try:
            cp = subprocess.run(
                argv, capture_output=True, text=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return KubectlOutput(
                success=False,
                summary=f"kubectl {command}: timed out after {self.timeout}s",
                stdout="", stderr="timeout", exit_code=-1,
                error="timeout",
            ).model_dump_json()
        except FileNotFoundError:
            return KubectlOutput(
                success=False,
                summary="kubectl binary not found on PATH",
                stdout="", stderr="", exit_code=-1,
                error="not_found",
            ).model_dump_json()
        except Exception as e:
            return KubectlOutput(
                success=False,
                summary=f"kubectl {command}: {e}",
                stdout="", stderr=str(e), exit_code=-1,
                error=str(e),
            ).model_dump_json()

        stdout = (cp.stdout or "").strip()
        stderr = (cp.stderr or "").strip()
        ok = cp.returncode == 0
        return KubectlOutput(
            success=ok,
            summary=(f"kubectl {command}: ok" if ok
                     else f"kubectl {command}: exit {cp.returncode}"),
            stdout=stdout, stderr=stderr, exit_code=cp.returncode,
            error=None if ok else stderr,
        ).model_dump_json()
```

- [ ] **Step 4: Run tests, expect pass**

Run: `pytest tests/test_kubectl.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add kubectl_agent.py tests/test_kubectl.py
git commit -m "feat(kubectl): add LocalKubectlAgent for host-local kubectl commands"
```

---

## Task 4: Planner module

**Files:**
- Create: `planner.py`
- Test: `tests/test_planner.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_planner.py`:

```python
import json
from unittest.mock import MagicMock
from planner import Planner, _strip_code_fences, _PLAN_INSTRUCTION
from tool_schemas import Plan


def _fake_router_returning(text: str):
    """Build a fake ModelRouter whose .get_llm().invoke(...) returns an AIMessage-like obj."""
    msg = MagicMock(); msg.content = text
    llm = MagicMock(); llm.invoke = MagicMock(return_value=msg)
    router = MagicMock(); router.get_llm = MagicMock(return_value=llm)
    return router, llm


def test_strip_code_fences():
    assert _strip_code_fences("```json\n{\"a\":1}\n```") == '{"a":1}'
    assert _strip_code_fences("```\n{\"a\":1}\n```") == '{"a":1}'
    assert _strip_code_fences('{"a":1}') == '{"a":1}'


def test_plan_parses_valid_json():
    valid = json.dumps({
        "reasoning": "two-step flow",
        "steps": [
            {"step_id": 1, "description": "list containers",
             "intended_tool": "RunDockerCommand", "success_criteria": "ps returns 0"},
            {"step_id": 2, "description": "report count",
             "intended_tool": "reasoning", "success_criteria": "user gets number"},
        ],
    })
    router, llm = _fake_router_returning(valid)
    p = Planner(router=router, tool_names=["RunDockerCommand", "reasoning"])
    plan = p.plan("count my containers")
    assert isinstance(plan, Plan)
    assert len(plan.steps) == 2
    assert plan.steps[0].intended_tool == "RunDockerCommand"


def test_plan_strips_fences():
    fenced = "```json\n" + json.dumps({
        "reasoning": "single", "steps": [
            {"step_id": 1, "description": "x", "intended_tool": "reasoning",
             "success_criteria": "ok"}]
    }) + "\n```"
    router, _ = _fake_router_returning(fenced)
    p = Planner(router=router, tool_names=["reasoning"])
    plan = p.plan("hi")
    assert plan.steps[0].description == "x"


def test_plan_retries_on_parse_error_then_succeeds():
    msg_bad = MagicMock(); msg_bad.content = "not json at all"
    valid = json.dumps({
        "reasoning": "fix", "steps": [
            {"step_id": 1, "description": "ok now", "intended_tool": "reasoning",
             "success_criteria": "ok"}]
    })
    msg_good = MagicMock(); msg_good.content = valid
    llm = MagicMock(); llm.invoke = MagicMock(side_effect=[msg_bad, msg_good])
    router = MagicMock(); router.get_llm = MagicMock(return_value=llm)
    p = Planner(router=router, tool_names=["reasoning"])
    plan = p.plan("hi")
    assert llm.invoke.call_count == 2
    assert plan.steps[0].description == "ok now"


def test_plan_returns_none_after_two_failures():
    bad = MagicMock(); bad.content = "still not json"
    llm = MagicMock(); llm.invoke = MagicMock(return_value=bad)
    router = MagicMock(); router.get_llm = MagicMock(return_value=llm)
    p = Planner(router=router, tool_names=["reasoning"])
    plan = p.plan("hi")
    assert plan is None
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_planner.py -v`
Expected: 5 failures — `planner` not importable.

- [ ] **Step 3: Implement `planner.py`**

```python
import json
import logging
import re
from typing import Optional
from pydantic import ValidationError

from tool_schemas import Plan

logger = logging.getLogger("synapse.planner")

_PLAN_INSTRUCTION = """You are SYNAPSE's planner. Given a user request and a list of available tools, output a JSON plan.

OUTPUT FORMAT — strict JSON, no markdown fences, no commentary:
{{
  "reasoning": "1-3 sentences on why this plan",
  "steps": [
    {{"step_id": 1, "description": "...", "intended_tool": "<tool name or 'reasoning'>",
      "success_criteria": "..."}},
    ...
  ]
}}

Rules:
- At most 10 steps. Each step is atomic — one tool call's worth of work.
- intended_tool must be one of: {tool_list} (or "reasoning" if no tool is needed).
- If a step is destructive (rm -rf, format, drop database), include the word "destructive" in the description.
- Return ONLY the JSON object."""


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    m = _FENCE_RE.match(text)
    if m:
        return m.group(1).strip()
    return text


class Planner:
    """Wraps the LLM to produce a Plan JSON from a user request."""

    def __init__(self, router, tool_names: list[str]):
        self.router = router
        self.tool_names = tool_names

    def _instruction(self) -> str:
        return _PLAN_INSTRUCTION.format(tool_list=", ".join(self.tool_names))

    def _invoke(self, prompt: str) -> str:
        llm = self.router.get_llm()
        response = llm.invoke([
            {"role": "system", "content": self._instruction()},
            {"role": "user", "content": prompt},
        ])
        return getattr(response, "content", str(response))

    def _parse(self, raw: str) -> Optional[Plan]:
        try:
            data = json.loads(_strip_code_fences(raw))
            return Plan(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning("Planner parse failed: %s", e)
            return None

    def plan(self, user_message: str, session_context: str = "") -> Optional[Plan]:
        """Returns Plan or None if parsing fails twice."""
        prompt = user_message
        if session_context:
            prompt = f"{session_context}\n\nUser request: {user_message}"

        raw = self._invoke(prompt)
        parsed = self._parse(raw)
        if parsed is not None:
            return parsed

        retry_prompt = (
            f"{prompt}\n\nYour previous reply was not valid JSON. "
            "Return ONLY the JSON object, no fences, no prose."
        )
        raw2 = self._invoke(retry_prompt)
        return self._parse(raw2)

    def replan(self, original: Plan, completed_step_ids: list[int],
               failure_context: str) -> Optional[Plan]:
        completed = [s for s in original.steps if s.step_id in completed_step_ids]
        completed_str = "\n".join(
            f"- step {s.step_id}: {s.description}" for s in completed
        ) or "(none)"
        prompt = (
            f"We were executing this plan:\n{original.model_dump_json()}\n\n"
            f"Completed steps:\n{completed_str}\n\n"
            f"Failure context: {failure_context}\n\n"
            "Produce a new plan that takes us from here to the user's original goal. "
            "Do not repeat completed steps."
        )
        raw = self._invoke(prompt)
        return self._parse(raw)
```

- [ ] **Step 4: Run tests, expect pass**

Run: `pytest tests/test_planner.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add planner.py tests/test_planner.py
git commit -m "feat(planner): add Planner module with JSON-plan + replan support"
```

---

## Task 5: Triage helper + final-answer composer

**Files:**
- Create: `orchestration.py`
- Test: `tests/test_orchestration.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_orchestration.py`:

```python
from orchestration import needs_planning, compose_final_answer
from tool_schemas import Plan, PlanStep, StepResult


def test_needs_planning_short_simple():
    assert needs_planning("kernel version") is False
    assert needs_planning("list pods") is False


def test_needs_planning_long_or_compound():
    assert needs_planning("build an image and run it and curl the endpoint") is True
    assert needs_planning("a b c d e f g h i j k") is True
    assert needs_planning("start a server, then check it") is True


def test_compose_final_all_done():
    plan = Plan(reasoning="r", steps=[
        PlanStep(step_id=1, description="d1", intended_tool="reasoning", success_criteria="ok"),
        PlanStep(step_id=2, description="d2", intended_tool="reasoning", success_criteria="ok"),
    ])
    results = [
        StepResult(step_id=1, status="done", summary="s1"),
        StepResult(step_id=2, status="done", summary="s2"),
    ]
    out = compose_final_answer(plan, results)
    assert "2/2" in out
    assert "d1" in out and "s1" in out


def test_compose_final_with_failure():
    plan = Plan(reasoning="r", steps=[
        PlanStep(step_id=1, description="d1", intended_tool="reasoning", success_criteria="ok"),
        PlanStep(step_id=2, description="d2", intended_tool="reasoning", success_criteria="ok"),
    ])
    results = [
        StepResult(step_id=1, status="done", summary="s1"),
        StepResult(step_id=2, status="failed", summary="boom"),
    ]
    out = compose_final_answer(plan, results)
    assert "1/2" in out
    assert "boom" in out
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_orchestration.py -v`
Expected: 4 failures — `orchestration` not importable.

- [ ] **Step 3: Implement `orchestration.py`**

```python
from tool_schemas import Plan, StepResult

_CONJUNCTIONS = (" and ", " then ", ",", ";")


def needs_planning(message: str) -> bool:
    """True if the prompt is multi-step enough to warrant a plan."""
    msg = message.strip()
    if len(msg.split()) > 8:
        return True
    lower = f" {msg.lower()} "
    return any(c in lower for c in _CONJUNCTIONS)


def compose_final_answer(plan: Plan, results: list[StepResult]) -> str:
    """Render a markdown summary of plan execution."""
    n_total = len(plan.steps)
    n_done = sum(1 for r in results if r.status == "done")
    by_id = {r.step_id: r for r in results}

    lines = [f"**Plan executed** ({n_done}/{n_total} steps completed)", ""]
    for step in plan.steps:
        r = by_id.get(step.step_id)
        if r is None:
            lines.append(f"{step.step_id}. {step.description} — _not run_")
        else:
            mark = "✓" if r.status == "done" else "✗"
            lines.append(f"{step.step_id}. {mark} {step.description} — {r.summary}")
    lines.append("")

    failed = [r for r in results if r.status == "failed"]
    if failed:
        lines.append("Failed steps:")
        for r in failed:
            lines.append(f"- step {r.step_id}: {r.summary}")
    else:
        if results:
            lines.append(results[-1].summary)
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests, expect pass**

Run: `pytest tests/test_orchestration.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add orchestration.py tests/test_orchestration.py
git commit -m "feat(orchestration): add needs_planning triage and compose_final_answer"
```

---

## Task 6: Executor module

**Files:**
- Create: `executor.py`
- Test: `tests/test_executor.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_executor.py`:

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tool_schemas import Plan, PlanStep
from executor import Executor


def _plan(*steps):
    return Plan(reasoning="r", steps=[
        PlanStep(step_id=i + 1, description=d, intended_tool="reasoning",
                 success_criteria="ok")
        for i, d in enumerate(steps)
    ])


def _exec(monkeyresults):
    """Build an Executor that returns canned ReAct results in order."""
    sio = MagicMock(); sio.emit = AsyncMock()
    planner = MagicMock()
    ex = Executor(
        llm=MagicMock(), tools=[], memory=MagicMock(),
        sio=sio, sid="sid1", planner=planner,
    )
    ex._run_react_step = AsyncMock(side_effect=list(monkeyresults))
    return ex, sio, planner


def test_run_plan_all_done():
    ex, sio, planner = _exec([
        ("done", "first ok", []),
        ("done", "second ok", []),
    ])
    plan = _plan("step one", "step two")
    results = asyncio.run(ex.run_plan(plan, session_id="s"))
    assert [r.status for r in results] == ["done", "done"]
    assert [r.summary for r in results] == ["first ok", "second ok"]


def test_run_plan_retry_then_succeed():
    ex, sio, planner = _exec([
        ("failed", "transient", []),  # first attempt of step 1
        ("done", "retry worked", []),  # retry succeeds
        ("done", "step 2 ok", []),
    ])
    plan = _plan("step one", "step two")
    results = asyncio.run(ex.run_plan(plan, session_id="s"))
    assert [r.status for r in results] == ["done", "done"]
    assert results[0].summary == "retry worked"


def test_run_plan_failure_triggers_replan():
    ex, sio, planner = _exec([
        ("failed", "first attempt fails", []),
        ("failed", "retry also fails", []),
        ("done", "replanned step ok", []),
    ])
    new_plan = _plan("replan-step")
    planner.replan = MagicMock(return_value=new_plan)
    plan = _plan("step one", "step two")
    results = asyncio.run(ex.run_plan(plan, session_id="s"))
    assert planner.replan.called
    statuses = [r.status for r in results]
    assert "done" in statuses


def test_run_plan_caps_replans_at_two():
    side = [("failed", f"f{i}", []) for i in range(10)]
    ex, sio, planner = _exec(side)
    planner.replan = MagicMock(side_effect=[_plan("p2"), _plan("p3"), _plan("p4")])
    plan = _plan("s1")
    results = asyncio.run(ex.run_plan(plan, session_id="s"))
    assert planner.replan.call_count <= 2
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_executor.py -v`
Expected: 4 failures — `executor` not importable.

- [ ] **Step 3: Implement `executor.py`**

```python
import logging
from typing import Any
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
                if '"success": false' in output or '"success":false' in output:
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

    async def run_plan(self, plan: Plan, session_id: str) -> list[StepResult]:
        results: list[StepResult] = []
        current_plan = plan
        i = 0
        while i < len(current_plan.steps):
            step = current_plan.steps[i]
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
```

- [ ] **Step 4: Run tests, expect pass**

Run: `pytest tests/test_executor.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add executor.py tests/test_executor.py
git commit -m "feat(executor): add Executor with retry-once + replan-twice failure handling"
```

---

## Task 7: Wire planner + executor + new tools into `main.py`

**Files:**
- Modify: `main.py` (replace docker import, add kubectl tool, add planner/executor wiring)

- [ ] **Step 1: Update imports and add Kubectl input schema reference**

Replace lines 16-25 of `main.py`:

```python
from linux_agent import LinuxAgent
from docker_agent import LocalDockerAgent as DockerAgent
from kubectl_agent import LocalKubectlAgent
from aws_agent import AWSAgent
from training_agent import TrainingAgent
from notification_agent import NotificationAgent
from github_actions_tool import github_actions_tool
from tool_schemas import GitHubActionsInput, KubectlCommandInput
from model_router import ModelRouter
from agent_memory import agent_memory
from agent_prompts import build_prompt
from planner import Planner
from executor import Executor
from orchestration import needs_planning, compose_final_answer
```

- [ ] **Step 2: Add `KubectlCommandInputSchema` to the input-class block**

After the `AWSCommandInput` class (around line 47), add:

```python
class KubectlCommandInputSchema(BaseModel):
    command: str = Field(description="kubectl arguments (everything after 'kubectl'). Example: 'get pods', 'apply -f deploy.yml'")
```

- [ ] **Step 3: Instantiate the kubectl agent and update Docker tool description**

Locate the agent instantiations (around `docker_agent = DockerAgent()`) and add `kubectl_agent = LocalKubectlAgent()`:

```python
linux_agent = LinuxAgent()
docker_agent = DockerAgent()
kubectl_agent = LocalKubectlAgent()
aws_agent = AWSAgent()
training_agent = TrainingAgent()
notification_agent = NotificationAgent()
```

In the `tools = [...]` list, update the Docker entry's description and add the kubectl tool right after it:

```python
    Tool(name="RunDockerCommand", func=docker_agent.run_command,
         args_schema=DockerCommandInput,
         description="Run a Docker CLI command on the local host. Docker Desktop must be installed and running."),
    Tool(name="RunKubectlCommand", func=kubectl_agent.run_command,
         args_schema=KubectlCommandInputSchema,
         description="Run a kubectl command on the local host. Kubernetes context must be configured on the host."),
```

- [ ] **Step 4: Log detection results at startup**

After `agent_executor = create_react_agent(llm, tools)` (around line 114), add:

```python
docker_err = docker_agent.detect()
if docker_err:
    logger.warning("Docker not available: %s", docker_err)
kubectl_err = kubectl_agent.detect()
if kubectl_err:
    logger.warning("kubectl not available: %s", kubectl_err)

planner = Planner(router=router, tool_names=[t.name for t in tools])
```

- [ ] **Step 5: Extract single-ReAct flow into helper and add planner branch**

Replace the entire body of `handle_command` (lines 127-185) with:

```python
async def _run_single_react(sid, session_id, query, session_context):
    system_prompt = build_prompt(session_context=session_context)
    agent = create_react_agent(llm, tools, state_modifier=system_prompt)
    full_response = []
    try:
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": query}]}, version="v2",
        ):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    await sio.emit("token", {"data": chunk.content}, to=sid)
                    full_response.append(chunk.content)
            elif kind == "on_tool_start":
                await sio.emit("tool_call", {
                    "tool": event["name"], "status": "running",
                    "input": str(event["data"].get("input", {}))[:200],
                }, to=sid)
            elif kind == "on_tool_end":
                tool_name = event["name"]
                tool_output = str(event["data"].get("output", ""))
                agent_memory.add(
                    session_id, role="tool", content=tool_output,
                    tool_name=tool_name, tool_result_summary=tool_output[:150],
                )
                await sio.emit("tool_call", {
                    "tool": tool_name, "status": "done",
                    "output": tool_output[:200],
                }, to=sid)
        final = "".join(full_response)
        agent_memory.add(session_id, role="agent", content=final[:300])
        await sio.emit("command_output", {"data": final}, to=sid)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Agent error sid={sid}: {error_msg}")
        await sio.emit("command_output", {"data": f"Error: {error_msg}"}, to=sid)


@sio.on("execute_natural_command")
async def handle_command(sid, data):
    query = data.get("command", "").strip()
    if not query:
        return
    session_id = sid

    agent_memory.add(session_id, role="user", content=query)
    session_context = agent_memory.get_context(session_id)

    if not needs_planning(query):
        await _run_single_react(sid, session_id, query, session_context)
        return

    plan = planner.plan(query, session_context)
    if plan is None:
        logger.warning("Planner failed; falling back to single-ReAct")
        await _run_single_react(sid, session_id, query, session_context)
        return

    await sio.emit("plan_generated", {"plan": plan.model_dump()}, to=sid)
    executor = Executor(
        llm=llm, tools=tools, memory=agent_memory,
        sio=sio, sid=sid, planner=planner,
    )
    try:
        results = await executor.run_plan(plan, session_id)
        final = compose_final_answer(plan, results)
        agent_memory.add(session_id, role="agent", content=final[:300])
        await sio.emit("command_output", {"data": final}, to=sid)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Executor error sid={sid}: {error_msg}")
        await sio.emit("command_output", {"data": f"Error: {error_msg}"}, to=sid)
```

- [ ] **Step 6: Verify import**

Run: `python -c "import main; print('ok')"`
Expected: `ok` printed (warnings about docker/kubectl detection are fine).

- [ ] **Step 7: Commit**

```bash
git add main.py
git commit -m "feat(main): wire planner+executor branch, add kubectl tool, switch docker to local"
```

---

## Task 8: Frontend — StepStatusIcon + PlanPanel components

**Files:**
- Create: `synapse/src/components/StepStatusIcon.tsx`
- Create: `synapse/src/components/PlanPanel.tsx`

- [ ] **Step 1: Create `StepStatusIcon.tsx`**

```tsx
import React from 'react';

export type StepStatus =
  | 'pending'
  | 'running'
  | 'done'
  | 'failed'
  | 'retry'
  | 'replanned';

const STYLES: Record<StepStatus, { glyph: string; cls: string }> = {
  pending:    { glyph: '○', cls: 'text-gray-500' },
  running:    { glyph: '◐', cls: 'text-cyan-300 animate-pulse' },
  done:       { glyph: '✓', cls: 'text-green-400' },
  failed:     { glyph: '✗', cls: 'text-red-400' },
  retry:      { glyph: '↻', cls: 'text-amber-300' },
  replanned:  { glyph: '★', cls: 'text-purple-400' },
};

interface Props { status: StepStatus; }

export const StepStatusIcon: React.FC<Props> = ({ status }) => {
  const s = STYLES[status] ?? STYLES.pending;
  return <span className={`font-mono text-sm ${s.cls}`}>{s.glyph}</span>;
};
```

- [ ] **Step 2: Create `PlanPanel.tsx`**

```tsx
import React from 'react';
import { StepStatusIcon, type StepStatus } from './StepStatusIcon';

export interface PlanStep {
  step_id: number;
  description: string;
  intended_tool: string;
  success_criteria: string;
}

export interface Plan {
  steps: PlanStep[];
  reasoning: string;
}

interface Props {
  plan: Plan | null;
  statuses: Record<number, { status: StepStatus; message?: string }>;
}

export const PlanPanel: React.FC<Props> = ({ plan, statuses }) => {
  if (!plan) {
    return (
      <div className="p-4 text-xs text-gray-500 uppercase tracking-widest">
        No plan yet — send a multi-step command to generate one.
      </div>
    );
  }

  return (
    <div className="p-4 overflow-y-auto h-full">
      <h2 className="font-orbitron text-cyan-400 text-sm tracking-widest mb-3">
        PLAN
      </h2>
      <p className="text-xs text-gray-400 mb-4 italic">{plan.reasoning}</p>
      <ol className="space-y-3">
        {plan.steps.map((step) => {
          const st = statuses[step.step_id]?.status ?? 'pending';
          const msg = statuses[step.step_id]?.message;
          return (
            <li
              key={step.step_id}
              className="border-l-2 border-cyan-500/30 pl-3 py-1"
            >
              <div className="flex items-start gap-2">
                <StepStatusIcon status={st} />
                <span className="text-xs text-gray-500 mt-0.5">
                  {step.step_id}.
                </span>
                <span className="text-sm text-gray-100 flex-1">
                  {step.description}
                </span>
              </div>
              <div className="mt-1 ml-6 flex items-center gap-2">
                <span className="text-[10px] uppercase tracking-wider bg-cyan-900/40 text-cyan-200 px-2 py-0.5 rounded">
                  {step.intended_tool}
                </span>
                {msg && (
                  <span className="text-[10px] text-gray-400 truncate">{msg}</span>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
};
```

- [ ] **Step 3: Verify TypeScript compiles**

Run from `synapse/`:
```
npm run build
```
Expected: build succeeds (or the only failures are unrelated to the new files).

- [ ] **Step 4: Commit**

```bash
git add synapse/src/components/StepStatusIcon.tsx synapse/src/components/PlanPanel.tsx
git commit -m "feat(ui): add PlanPanel and StepStatusIcon components"
```

---

## Task 9: Frontend — two-pane layout in `App.tsx` and tone-down particles

**Files:**
- Modify: `synapse/src/App.tsx`
- Modify: `synapse/src/components/ParticleBackground.tsx`

- [ ] **Step 1: Tone down `ParticleBackground.tsx` (find the particle count and opacity)**

Open `synapse/src/components/ParticleBackground.tsx`. Find the constant that controls particle count (typically `numParticles`, `PARTICLE_COUNT`, or similar). Halve it. Find the rendering opacity (alpha or globalAlpha) and reduce by ~30%. If neither exists, wrap the rendered canvas in a parent `<div style={{ opacity: 0.6 }}>`.

Verify the change is the only edit by running `git diff synapse/src/components/ParticleBackground.tsx` — should be a small numeric/style change only.

- [ ] **Step 2: Replace `App.tsx` with two-pane layout + new socket events**

```tsx
import { useState, useEffect } from 'react';
import { socket } from './socket';
import { ChatDisplay } from './components/ChatDisplay';
import type { Message } from './components/ChatDisplay';
import { InputBar } from './components/InputBar';
import { EntryScreen } from './components/EntryScreen';
import { ParticleBackground } from './components/ParticleBackground';
import { ModelIndicator } from './components/ModelIndicator';
import { PlanPanel, type Plan } from './components/PlanPanel';
import type { StepStatus } from './components/StepStatusIcon';

type StepStateMap = Record<number, { status: StepStatus; message?: string }>;

function App() {
  const [showEntryScreen, setShowEntryScreen] = useState(true);
  const [isConnected, setIsConnected] = useState(socket.connected);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [stepStatuses, setStepStatuses] = useState<StepStateMap>({});

  const handleSendMessage = (message: string) => {
    if (message.trim() === '') return;
    socket.emit('execute_natural_command', { command: message });
    setMessages((prev) => [...prev, { text: message, user: 'You' }]);
    setIsTyping(true);
    setPlan(null);
    setStepStatuses({});
  };

  useEffect(() => {
    const onConnect = () => setIsConnected(true);
    const onDisconnect = () => setIsConnected(false);
    const onCommandOutput = (data: { data: string }) => {
      setIsTyping(false);
      setMessages((prev) => [...prev, { text: data.data, user: 'SYNAPSE' }]);
    };
    const onPlanGenerated = (data: { plan: Plan; replanned?: boolean }) => {
      setPlan(data.plan);
      if (!data.replanned) setStepStatuses({});
    };
    const onStepStatus = (data: {
      step_id: number;
      status: StepStatus;
      message?: string;
    }) => {
      setStepStatuses((prev) => ({
        ...prev,
        [data.step_id]: { status: data.status, message: data.message },
      }));
    };

    socket.on('connect', onConnect);
    socket.on('disconnect', onDisconnect);
    socket.on('command_output', onCommandOutput);
    socket.on('plan_generated', onPlanGenerated);
    socket.on('step_status', onStepStatus);

    return () => {
      socket.off('connect', onConnect);
      socket.off('disconnect', onDisconnect);
      socket.off('command_output', onCommandOutput);
      socket.off('plan_generated', onPlanGenerated);
      socket.off('step_status', onStepStatus);
    };
  }, []);

  return (
    <>
      <ParticleBackground />
      {showEntryScreen ? (
        <EntryScreen onEnter={() => setShowEntryScreen(false)} />
      ) : (
        <div className="flex flex-col h-screen bg-transparent text-gray-200 animate-fade-in">
          <header className="p-4 text-center border-b border-cyan-500/20 bg-black/30 backdrop-blur-sm">
            <h1 className="font-orbitron text-2xl font-bold text-cyan-400 drop-shadow-[0_0_8px_rgba(0,255,255,0.6)]">
              S Y N A P S E
            </h1>
            <p className={`text-xs uppercase tracking-widest ${isConnected ? 'text-green-400' : 'text-red-400'}`}>
              {isConnected ? '● SYSTEM ONLINE' : '● CONNECTION LOST'}
            </p>
            <div className="mt-1 flex justify-center">
              <ModelIndicator />
            </div>
          </header>

          <div className="flex flex-1 min-h-0">
            <aside className="hidden md:block w-80 border-r border-cyan-500/20 bg-black/20 backdrop-blur-sm">
              <PlanPanel plan={plan} statuses={stepStatuses} />
            </aside>
            <main className="flex flex-col flex-1 min-w-0">
              <div className="md:hidden">
                {plan && (
                  <details className="border-b border-cyan-500/20 bg-black/20">
                    <summary className="px-4 py-2 text-xs uppercase tracking-widest text-cyan-300 cursor-pointer">
                      Plan ({plan.steps.length} steps)
                    </summary>
                    <PlanPanel plan={plan} statuses={stepStatuses} />
                  </details>
                )}
              </div>
              <ChatDisplay messages={messages} isTyping={isTyping} />
              <InputBar onSendMessage={handleSendMessage} />
            </main>
          </div>
        </div>
      )}
    </>
  );
}

export default App;
```

- [ ] **Step 3: Run the frontend build**

Run from `synapse/`:
```
npm run build
```
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add synapse/src/App.tsx synapse/src/components/ParticleBackground.tsx
git commit -m "feat(ui): two-pane mission-control layout with plan panel and live step statuses"
```

---

## Task 10: Manual smoke test

**Files:** none modified.

- [ ] **Step 1: Start the backend**

From the project root, run `python start_backend.py` (or `uvicorn main:app --reload`). Watch the log for:
- `SYNAPSE started. LLM provider: <name>` — required.
- `Docker not available: ...` — only if Docker Desktop isn't running; non-fatal.
- `kubectl not available: ...` — only if kubectl isn't installed; non-fatal.

- [ ] **Step 2: Start the frontend**

From `synapse/`, run `npm run dev`. Open the printed URL in a browser. Confirm the entry screen renders, then click through to the main UI.

- [ ] **Step 3: Trivial single-step prompt**

Send: `ls`

Expected:
- Plan panel stays empty (says "No plan yet…").
- ChatDisplay shows the SYNAPSE response.

- [ ] **Step 4: Compound multi-step prompt (host-local Docker)**

Send: `pull the alpine:latest docker image and tell me how many images I have now`

Expected:
- `plan_generated` arrives — plan panel shows 2+ steps with intended tool `RunDockerCommand`.
- Each step transitions pending → running → done.
- Final chat message starts with `**Plan executed**` and includes the image count.

- [ ] **Step 5: Failure + replan**

Send: `pull the image named definitely-not-a-real-image:no and then list my images`

Expected:
- Step 1 transitions running → failed (or retry → failed).
- Plan panel shows a `★` replanned indicator on a new plan.
- Final summary acknowledges the failure but still lists images.

- [ ] **Step 6: No commit (smoke test only).** If any step above fails, file an issue or fix and re-run the relevant earlier task.

---

## Self-Review

**Spec coverage** — every spec section maps to a task:
- §3 Planner → Task 4.
- §4 Executor → Task 6.
- §5 Local Docker → Task 2.
- §6 Kubectl → Task 3.
- §7 UI panels → Tasks 8, 9.
- §8 New events → emitted in Tasks 6, 7; consumed in Task 9.
- §9 main.py wiring → Task 7.
- §10 Build Order — matches task numbering with the small adjustment that triage+composer (Task 5) is split out before main.py wiring so main.py imports already exist.
- §11 Tests — Tasks 2, 3, 4, 5, 6 each ship pytest tests.

**Placeholders** — none.

**Type consistency** — `Plan`, `PlanStep`, `StepResult` are defined in Task 1 (`tool_schemas.py`) and imported with the same names everywhere they appear (planner, executor, orchestration, App.tsx mirror). `StepStatus` literal in `StepStatusIcon.tsx` matches the backend emit values from Task 6's executor.
