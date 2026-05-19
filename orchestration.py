from tool_schemas import Plan, StepResult

# Conjunctions that strongly suggest a multi-step intent.
# Comma/semicolon must be followed by a space to avoid matching CLI flags
# like "-n default,kube-system" where the comma is intra-token.
_CONJUNCTIONS = (" and ", " then ", ", ", "; ")
_ACTION_WORDS = {
    "apply", "build", "check", "configure", "create", "curl", "deploy",
    "email", "install", "launch", "notify", "provision", "restart", "run",
    "send", "start", "stop", "telegram", "test", "trigger", "wait",
}
_NOTIFICATION_WORDS = {"email", "sms", "telegram", "notify", "message"}


def needs_planning(message: str) -> bool:
    """True if the prompt is multi-step enough to warrant a plan."""
    msg = message.strip()
    lower = f" {msg.lower()} "
    if any(c in lower for c in _CONJUNCTIONS):
        return True

    words = {w.strip(".,;:!?()[]{}'\"").lower() for w in msg.split()}
    action_count = len(words & _ACTION_WORDS)
    asks_for_notification = bool(words & _NOTIFICATION_WORDS)
    return action_count >= 2 or (asks_for_notification and action_count >= 1)


def compose_final_answer(plan: Plan, results: list[StepResult]) -> str:
    """Render a markdown summary of plan execution.

    A step can have multiple StepResult entries when an initial attempt failed
    and a later replan succeeded for the same step_id. The latest result wins
    for the top list, and a step that ultimately succeeded must NOT appear in
    the "Failed steps" section.
    """
    done_ids = {r.step_id for r in results if r.status == "done"}
    n_total = len(plan.steps)
    n_done = sum(1 for s in plan.steps if s.step_id in done_ids)
    # Keep the LAST result per step_id (replan success overrides earlier failure).
    by_id: dict[int, StepResult] = {}
    for r in results:
        by_id[r.step_id] = r

    lines = [f"**Plan executed** ({n_done}/{n_total} steps completed)", ""]
    for step in plan.steps:
        r = by_id.get(step.step_id)
        if r is None:
            lines.append(f"{step.step_id}. {step.description} — _not run_")
        else:
            mark = "✓" if r.status == "done" else "✗"
            lines.append(f"{step.step_id}. {mark} {step.description} — {r.summary}")
    lines.append("")

    # Only list steps that ultimately failed (no later success for that step_id).
    failed = [
        r for r in results
        if r.status == "failed" and r.step_id not in done_ids
    ]
    if failed:
        lines.append("Failed steps:")
        for r in failed:
            lines.append(f"- step {r.step_id}: {r.summary}")
    elif results:
        last_done = next(
            (r for r in reversed(results) if r.status == "done"),
            results[-1],
        )
        lines.append(last_done.summary)
    return "\n".join(lines)
