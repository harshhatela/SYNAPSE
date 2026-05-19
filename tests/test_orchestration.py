from orchestration import needs_planning, compose_final_answer
from tool_schemas import Plan, PlanStep, StepResult


def test_needs_planning_short_simple():
    assert needs_planning("kernel version") is False
    assert needs_planning("list pods") is False


def test_needs_planning_long_or_compound():
    assert needs_planning("build an image and run it and curl the endpoint") is True
    assert needs_planning("show running containers with ports sorted by name") is False
    assert needs_planning("start container send sms") is True
    assert needs_planning("start a server, then check it") is True


def test_needs_planning_intra_token_comma_is_not_compound():
    # CLI argument with comma-joined values like "-n default,kube-system"
    # should NOT trigger planning.
    assert needs_planning("kubectl get pods -n a,b") is False


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


def test_compose_final_step_failed_then_succeeded_on_replan():
    """A step that initially failed but later succeeded on replan must NOT
    appear in the 'Failed steps' list, and the count must reflect the success."""
    plan = Plan(reasoning="r", steps=[
        PlanStep(step_id=1, description="d1", intended_tool="reasoning", success_criteria="ok"),
        PlanStep(step_id=2, description="d2", intended_tool="reasoning", success_criteria="ok"),
    ])
    # Original step 1 failed, replan executed step 1 successfully, then step 2 failed.
    results = [
        StepResult(step_id=1, status="failed", summary="initial failure"),
        StepResult(step_id=1, status="done", summary="recovered on replan"),
        StepResult(step_id=2, status="failed", summary="step 2 broken"),
    ]
    out = compose_final_answer(plan, results)
    # Step 1 counts as done.
    assert "1/2" in out
    # Top list shows step 1 as ✓ with the recovery summary.
    assert "✓ d1" in out
    assert "recovered on replan" in out
    # Failed steps section lists step 2 only — NOT step 1.
    assert "step 2: step 2 broken" in out
    assert "initial failure" not in out
