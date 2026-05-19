import json
import logging
import re
from typing import Optional
from pydantic import ValidationError

from model_router import is_rate_limit_error
from tool_schemas import Plan

logger = logging.getLogger("synapse.planner")

_PLAN_INSTRUCTION = """You are SYNAPSE's planner. Given a user request and a list of available tools, output a JSON plan.

OUTPUT FORMAT - strict JSON, no markdown fences, no commentary:
{{
  "reasoning": "1-3 sentences on why this plan",
  "steps": [
    {{"step_id": 1, "description": "...", "intended_tool": "<tool name or 'reasoning'>",
      "success_criteria": "..."}},
    ...
  ]
}}

Rules:
- At most 10 steps. Each step is atomic - one tool call's worth of work.
- intended_tool must be one of: {tool_list} (or "reasoning" if no tool is needed).
- If a step is destructive (rm -rf, format, drop database), include the word "destructive" in the description.
- Destructive commands are blocked by tools unless the actual command argument is
  prefixed with `CONFIRMED:`. Only use that prefix when the user's request
  explicitly confirms the destructive action.
- Return ONLY the JSON object.

## Docker patterns (apply when the request involves containers)
- Port mapping, naming, env vars, and detached mode are flags on `docker run` and CANNOT
  be added afterwards. Bundle "start the container with port X exposed, named Y, running
  command Z" into a SINGLE step. Never plan a separate "expose port" step — there is no
  such Docker operation.
- For Python / Flask container work, prefer `python:3.11-slim`. Do NOT use `centos:latest`
  (no longer published on Docker Hub).
- Always pass `--name <name>` and `-d` so later steps can reference the container by a
  predictable literal name.
- The docker tool does not run through a shell. Plans must not contain `$(...)`,
  backticks, pipes, or `&&` inside a single docker command argument. If you need to
  combine commands inside the container, use `bash -c "cmd1 && cmd2"` as the container
  command (those arguments ARE interpreted by bash inside the container).
- **`docker build` REQUIRES a build context path** (a directory) as its last positional
  argument. `docker build -t img -f Dockerfile` ALONE will fail with "requires 1 argument".
  Always end the command with `.` or a directory path:
  `build -t myimage -f C:\\tmp\\Dockerfile C:\\tmp\\`  ✅
  `build -t myimage -f C:\\tmp\\Dockerfile`             ❌

## File creation is NEVER `reasoning`
- Creating a Dockerfile, app.py, deploy.yml, config file, or any other artifact is a
  state-changing operation and MUST use a real tool, never `intended_tool: "reasoning"`.
- Pick the writing tool that matches where the file will be CONSUMED:
  - File consumed by `RunDockerCommand` / `RunKubectlCommand` (local Windows host):
    use `RunPowerShellCommand` with `Set-Content -Path 'C:\\tmp\\Dockerfile' -Value '...'`
    or use a here-string. Put the file in a Windows path (e.g. `C:\\tmp\\`).
  - File consumed by `RunShellCommand` (remote RHEL server):
    use `CreateRemoteFile` with an absolute Linux path (e.g. `/home/user/Dockerfile`).
- Match the host: a Dockerfile at `/home/user/Dockerfile` is invisible to local Docker
  Desktop on Windows. A Dockerfile at `C:\\tmp\\Dockerfile` is invisible to the RHEL server.

## Local vs remote tool selection
- If the request mentions "RHEL server", "remote server", "the server", a Dockerfile on
  the server, or anything implying SSH-reachable infrastructure: use RunShellCommand
  (which executes via SSH on the remote RHEL host). For Docker work on that host, that
  means `docker build`, `docker run`, etc. issued through RunShellCommand — NOT
  RunDockerCommand.
- If the request is about containers without server context (or mentions "locally" /
  "on my machine"): use RunDockerCommand (local Docker Desktop).

## AWS patterns
- Use `aws ec2 wait instance-running --instance-ids <id>` to block until an instance is
  running. This is a single tool call — do not plan polling loops.
- For EC2 launch, choose an SSM-resolved AMI to avoid hardcoding region-specific IDs:
  `--image-id resolve:ssm:/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2`.
- Use `--query` and `--output text` to extract single values like `PublicIpAddress` so
  the next step can quote them literally.

## Notification rule
Only plan a notification step if the user explicitly asks for one.

## Worked examples

User: "spin up a flask hello world container on port 8080 and telegram me the container id"
Output:
{{
  "reasoning": "One docker run handles image, port, name, install, and app start. Then capture the id from docker inspect and send via Telegram.",
  "steps": [
    {{"step_id": 1, "description": "Start a python:3.11-slim container named flask-hello in detached mode, map host port 8080 to container 8080, install Flask, and launch a Hello World app", "intended_tool": "RunDockerCommand", "success_criteria": "container running and bound to port 8080"}},
    {{"step_id": 2, "description": "Inspect the flask-hello container to retrieve its full container ID", "intended_tool": "RunDockerCommand", "success_criteria": "container ID captured"}},
    {{"step_id": 3, "description": "Send a Telegram notification containing the container ID from step 2", "intended_tool": "SendTelegramNotification", "success_criteria": "Telegram message delivered"}}
  ]
}}

User: "build a custom Dockerfile with Flask and run it on port 8080 locally"
Output:
{{
  "reasoning": "Local Docker means Dockerfile must be on the Windows host. Write it with PowerShell, build with a context path, then run with port mapping.",
  "steps": [
    {{"step_id": 1, "description": "Create C:\\\\tmp\\\\flask-app\\\\Dockerfile on the local Windows host containing 'FROM python:3.11-slim\\\\nRUN pip install flask\\\\nCOPY app.py /app.py\\\\nCMD python /app.py'", "intended_tool": "RunPowerShellCommand", "success_criteria": "Dockerfile written to disk"}},
    {{"step_id": 2, "description": "Create C:\\\\tmp\\\\flask-app\\\\app.py with a minimal Flask Hello World app bound to 0.0.0.0:8080", "intended_tool": "RunPowerShellCommand", "success_criteria": "app.py written to disk"}},
    {{"step_id": 3, "description": "Build the image tagged myflask using the Dockerfile and context directory: build -t myflask C:\\\\tmp\\\\flask-app", "intended_tool": "RunDockerCommand", "success_criteria": "image built"}},
    {{"step_id": 4, "description": "Run the myflask image detached, named myflask-run, with -p 8080:8080", "intended_tool": "RunDockerCommand", "success_criteria": "container running on port 8080"}}
  ]
}}

User: "build a docker image called myapp from the Dockerfile on the RHEL server, run it on port 5000, curl the health endpoint and SMS me the response"
Output:
{{
  "reasoning": "Docker work happens on the remote RHEL host, so use RunShellCommand (SSH). Build, run with -p, curl, then SMS the response.",
  "steps": [
    {{"step_id": 1, "description": "Build the docker image tagged myapp from the current directory on the RHEL server (docker build -t myapp .)", "intended_tool": "RunShellCommand", "success_criteria": "image built"}},
    {{"step_id": 2, "description": "Run the myapp image on the RHEL server, detached, name myapp-run, port 5000 mapped (docker run -d --name myapp-run -p 5000:5000 myapp)", "intended_tool": "RunShellCommand", "success_criteria": "container running on port 5000"}},
    {{"step_id": 3, "description": "Curl http://localhost:5000/health on the RHEL server and capture the response body", "intended_tool": "RunShellCommand", "success_criteria": "health endpoint returned a response"}},
    {{"step_id": 4, "description": "Send an SMS containing the health response captured in step 3", "intended_tool": "SendSMSNotification", "success_criteria": "SMS delivered"}}
  ]
}}

User: "spin up an EC2 t2.micro instance, wait for it to be running, then email me the public IP address"
Output:
{{
  "reasoning": "Use the SSM-resolved Amazon Linux AMI to launch a t2.micro, wait via aws ec2 wait, query the public IP, then email.",
  "steps": [
    {{"step_id": 1, "description": "Launch a t2.micro EC2 instance using the SSM-resolved Amazon Linux 2 AMI; capture the InstanceId from the output", "intended_tool": "RunAWSCommand", "success_criteria": "instance launched and InstanceId captured"}},
    {{"step_id": 2, "description": "Wait for the instance from step 1 to reach the running state using aws ec2 wait instance-running with the captured InstanceId", "intended_tool": "RunAWSCommand", "success_criteria": "instance in running state"}},
    {{"step_id": 3, "description": "Describe the instance from step 1 and extract its PublicIpAddress with --query and --output text", "intended_tool": "RunAWSCommand", "success_criteria": "public IP captured"}},
    {{"step_id": 4, "description": "Send an email with subject 'EC2 instance ready' and a body containing the public IP from step 3", "intended_tool": "SendEmailNotification", "success_criteria": "email delivered"}}
  ]
}}"""


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)

_TOOL_CALL_LEAKAGE_RES = (
    re.compile(r"\[TOOL_CALLS\]"),
    re.compile(r"\*\*Calling function [^*]+\*\*"),
    re.compile(r'\s*\{"command":[^}]+\}\s*'),
)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    m = _FENCE_RE.match(text)
    if m:
        return m.group(1).strip()
    return text


def _strip_tool_call_leakage(text: str) -> str:
    """Remove tool-call protocol fragments that some local models emit as prose."""
    out = text
    for pat in _TOOL_CALL_LEAKAGE_RES:
        out = pat.sub("", out)
    return out.strip()


class Planner:
    """Wraps the LLM to produce a Plan JSON from a user request."""

    def __init__(self, router, tool_names: list[str]):
        self.router = router
        self.tool_names = tool_names

    def _instruction(self) -> str:
        return _PLAN_INSTRUCTION.format(tool_list=", ".join(self.tool_names))

    def _invoke(self, prompt: str) -> str:
        messages = [
            {"role": "system", "content": self._instruction()},
            {"role": "user", "content": prompt},
        ]
        clients = self.router.get_clients_ordered()
        if not clients:
            raise RuntimeError("Planner: no LLM clients available")
        last_exc: BaseException | None = None
        for provider, client in clients:
            try:
                response = client.invoke(messages)
                return getattr(response, "content", str(response))
            except Exception as e:
                if is_rate_limit_error(e):
                    logger.warning("Planner: %s rate-limited; trying next provider", provider)
                    last_exc = e
                    continue
                raise
        raise RuntimeError(f"Planner: all providers rate-limited. Last: {last_exc}")

    def _parse(self, raw: str) -> Optional[Plan]:
        try:
            data = json.loads(_strip_code_fences(raw))
            plan = Plan(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning("Planner parse failed: %s", e)
            return None
        # Some local models leak tool-call protocol markers into descriptions.
        # Scrub them so the UI doesn't render "[TOOL_CALLS]**Calling function..."
        for step in plan.steps:
            step.description = _strip_tool_call_leakage(step.description)
        return plan if self._validate_plan(plan) else None

    def _validate_plan(self, plan: Plan) -> bool:
        allowed_tools = set(self.tool_names) | {"reasoning"}
        if not plan.steps:
            logger.warning("Planner returned no steps")
            return False
        if len(plan.steps) > 10:
            logger.warning("Planner returned too many steps: %s", len(plan.steps))
            return False

        seen: set[int] = set()
        for step in plan.steps:
            if step.step_id in seen:
                logger.warning("Planner returned duplicate step_id: %s", step.step_id)
                return False
            seen.add(step.step_id)
            if step.step_id < 1:
                logger.warning("Planner returned invalid step_id: %s", step.step_id)
                return False
            if step.intended_tool not in allowed_tools:
                logger.warning("Planner returned unknown tool: %s", step.intended_tool)
                return False
            if not step.description.strip() or not step.success_criteria.strip():
                logger.warning("Planner returned an empty description or success criteria")
                return False
        return True

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
