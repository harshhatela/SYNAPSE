import os
import time
import httpx
from langchain_core.tools import tool
from tool_schemas import GitHubActionsInput, GitHubActionsOutput

GITHUB_API = "https://api.github.com"


def _headers() -> dict:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN not set in environment. Required for GitHub Actions tool.")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


@tool("GitHubActions", args_schema=GitHubActionsInput)
def github_actions_tool(
    owner: str,
    repo: str,
    workflow_id: str,
    ref: str = "main",
    inputs: dict = None,
    action: str = "trigger",
    run_id: int = None,
) -> str:
    """
    Control GitHub Actions CI/CD workflows.
    Actions: trigger (start a run), status (check a run by run_id), list (last 5 runs).
    After triggering, call status with the returned run_id every 15 seconds until conclusion is not null.
    """
    try:
        if action == "trigger":
            return _trigger_workflow(owner, repo, workflow_id, ref, inputs or {})
        elif action == "status":
            if not run_id:
                return GitHubActionsOutput(
                    success=False, summary="run_id required for status check",
                    error="Missing run_id"
                ).model_dump_json()
            return _get_run_status(owner, repo, run_id)
        elif action == "list":
            return _list_runs(owner, repo, workflow_id)
        return GitHubActionsOutput(
            success=False, summary=f"Unknown action: {action}",
            error="action must be one of: trigger, status, list"
        ).model_dump_json()
    except Exception as e:
        return GitHubActionsOutput(
            success=False, summary=f"GitHub Actions error: {e}", error=str(e)
        ).model_dump_json()


def _trigger_workflow(owner, repo, workflow_id, ref, inputs):
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"
    with httpx.Client() as client:
        client.post(url, headers=_headers(), json={"ref": ref, "inputs": inputs}).raise_for_status()
    time.sleep(2)
    run_id = _find_latest_run_id(owner, repo, workflow_id, ref)
    run_url = f"https://github.com/{owner}/{repo}/actions/runs/{run_id}" if run_id else None
    return GitHubActionsOutput(
        success=run_id is not None,
        summary=f"Workflow '{workflow_id}' triggered on {ref}. Run ID: {run_id}",
        run_id=run_id, run_url=run_url, status="queued",
        error=None if run_id else "Workflow dispatched, but no matching run was found yet",
    ).model_dump_json()


def _find_latest_run_id(owner, repo, workflow_id, ref=None) -> int | None:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
    with httpx.Client() as client:
        params = {"per_page": 5}
        if ref:
            params["branch"] = ref
        resp = client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        runs = resp.json().get("workflow_runs", [])
        return runs[0]["id"] if runs else None


def _get_run_status(owner, repo, run_id):
    with httpx.Client() as client:
        run_resp = client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}", headers=_headers()
        )
        run_resp.raise_for_status()
        jobs_resp = client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs", headers=_headers()
        )
        jobs_resp.raise_for_status()
        data = run_resp.json()
        jobs = jobs_resp.json().get("jobs", [])[:5]

    status = data["status"]
    conclusion = data.get("conclusion")
    summary = f"Run {run_id}: {status}" + (f" -> {conclusion}" if conclusion else "")

    return GitHubActionsOutput(
        success=conclusion in [None, "success"],
        summary=summary,
        run_id=run_id,
        run_url=data["html_url"],
        status=status,
        conclusion=conclusion,
        workflow_name=data.get("name"),
        jobs=[{
            "name": j["name"],
            "status": j["status"],
            "conclusion": j.get("conclusion"),
        } for j in jobs],
    ).model_dump_json()


def _list_runs(owner, repo, workflow_id):
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
    with httpx.Client() as client:
        resp = client.get(url, headers=_headers(), params={"per_page": 5})
        resp.raise_for_status()
        runs = resp.json().get("workflow_runs", [])
    return GitHubActionsOutput(
        success=True,
        summary=f"Found {len(runs)} recent runs for {workflow_id}",
        jobs=[{"run_id": r["id"], "status": r["status"], "conclusion": r.get("conclusion"),
               "created_at": r["created_at"], "url": r["html_url"]} for r in runs],
    ).model_dump_json()
