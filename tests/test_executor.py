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


def test_tool_output_signals_failure_parses_json():
    # Real Pydantic-serialized failures should be detected.
    assert Executor._tool_output_signals_failure('{"success": false, "summary": "x"}') is True
    assert Executor._tool_output_signals_failure('{"success":  false}') is True
    assert Executor._tool_output_signals_failure('{"success": true}') is False
    # Non-JSON should not register as failure (the substring heuristic would).
    assert Executor._tool_output_signals_failure('error: "success": false in log') is False
    # Empty or malformed payloads return False without raising.
    assert Executor._tool_output_signals_failure("") is False
    assert Executor._tool_output_signals_failure("not json") is False


def test_run_plan_replan_skips_already_completed_steps():
    # First plan: 2 steps. Step 1 succeeds, step 2 fails twice -> replan.
    # Replan returns a plan containing step_id=1 (already done) + step_id=3 (new work).
    # Step 1 must be skipped; step 3 must run.
    replanned_calls = []
    def record_replan(*args, **kwargs):
        replanned_calls.append(kwargs)
        return Plan(reasoning="r", steps=[
            PlanStep(step_id=1, description="already done", intended_tool="reasoning", success_criteria="ok"),
            PlanStep(step_id=3, description="new work", intended_tool="reasoning", success_criteria="ok"),
        ])

    ex, sio, planner = _exec([
        ("done", "step1 ok", []),         # step 1 of original plan
        ("failed", "step2 fail", []),      # step 2 first attempt
        ("failed", "step2 retry fail", []),  # step 2 retry
        ("done", "step3 ok", []),          # step 3 of replanned plan (step 1 is skipped)
    ])
    planner.replan = MagicMock(side_effect=record_replan)

    plan = _plan("step one", "step two")
    results = asyncio.run(ex.run_plan(plan, session_id="s"))

    # We should NOT have a second StepResult for step_id=1.
    step1_results = [r for r in results if r.step_id == 1]
    assert len(step1_results) == 1
    assert step1_results[0].summary == "step1 ok"
    # Step 3 from the replanned plan must have run.
    assert any(r.step_id == 3 and r.status == "done" for r in results)
    # _run_react_step was called exactly 4 times (1 + 2 + 1), not 5.
    assert ex._run_react_step.call_count == 4
