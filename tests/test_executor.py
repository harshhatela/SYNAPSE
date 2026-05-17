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
