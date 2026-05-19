import json
from unittest.mock import MagicMock
from planner import Planner, _strip_code_fences, _strip_tool_call_leakage, _PLAN_INSTRUCTION
from tool_schemas import Plan


def _fake_router_returning(text: str):
    """Build a fake ModelRouter whose iterated client returns an AIMessage-like obj."""
    msg = MagicMock(); msg.content = text
    llm = MagicMock(); llm.invoke = MagicMock(return_value=msg)
    router = MagicMock()
    router.get_clients_ordered = MagicMock(return_value=[("groq", llm)])
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
    router = MagicMock()
    router.get_clients_ordered = MagicMock(return_value=[("groq", llm)])
    p = Planner(router=router, tool_names=["reasoning"])
    plan = p.plan("hi")
    assert llm.invoke.call_count == 2
    assert plan.steps[0].description == "ok now"


def test_plan_returns_none_after_two_failures():
    bad = MagicMock(); bad.content = "still not json"
    llm = MagicMock(); llm.invoke = MagicMock(return_value=bad)
    router = MagicMock()
    router.get_clients_ordered = MagicMock(return_value=[("groq", llm)])
    p = Planner(router=router, tool_names=["reasoning"])
    plan = p.plan("hi")
    assert plan is None


def test_plan_fails_over_to_next_provider_on_rate_limit():
    """Planner skips a rate-limited provider and uses the next one."""
    valid = json.dumps({
        "reasoning": "fallback path", "steps": [
            {"step_id": 1, "description": "ok", "intended_tool": "reasoning",
             "success_criteria": "ok"}]
    })
    msg_good = MagicMock(); msg_good.content = valid
    groq = MagicMock()
    groq.invoke = MagicMock(side_effect=Exception("Error code: 429 rate limit"))
    gemini = MagicMock(); gemini.invoke = MagicMock(return_value=msg_good)
    router = MagicMock()
    router.get_clients_ordered = MagicMock(return_value=[("groq", groq), ("gemini", gemini)])
    p = Planner(router=router, tool_names=["reasoning"])
    plan = p.plan("hi")
    assert plan is not None
    assert plan.steps[0].description == "ok"
    groq.invoke.assert_called_once()
    gemini.invoke.assert_called_once()


def test_plan_rejects_unknown_tool():
    invalid = json.dumps({
        "reasoning": "bad tool", "steps": [
            {"step_id": 1, "description": "do it", "intended_tool": "NopeTool",
             "success_criteria": "ok"}]
    })
    router, _ = _fake_router_returning(invalid)
    p = Planner(router=router, tool_names=["RunDockerCommand"])
    assert p.plan("hi") is None


def test_plan_rejects_duplicate_step_ids():
    invalid = json.dumps({
        "reasoning": "bad ids", "steps": [
            {"step_id": 1, "description": "first", "intended_tool": "reasoning",
             "success_criteria": "ok"},
            {"step_id": 1, "description": "second", "intended_tool": "reasoning",
             "success_criteria": "ok"}]
    })
    router, _ = _fake_router_returning(invalid)
    p = Planner(router=router, tool_names=["RunDockerCommand"])
    assert p.plan("hi") is None
