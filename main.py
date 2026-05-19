from dotenv import load_dotenv
load_dotenv()

import logging
import os
import uuid
from typing import Optional

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.tools import StructuredTool, Tool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from linux_agent import LinuxAgent
from docker_agent import LocalDockerAgent as DockerAgent
from kubectl_agent import LocalKubectlAgent
from powershell_agent import LocalPowerShellAgent
from aws_agent import AWSAgent
from training_agent import TrainingAgent
from notification_agent import NotificationAgent
from github_actions_tool import github_actions_tool
from model_router import ModelRouter, is_rate_limit_error
from agent_memory import agent_memory
from agent_prompts import build_prompt
from planner import Planner
from executor import Executor
from orchestration import needs_planning, compose_final_answer

log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(level=log_level)
logger = logging.getLogger("synapse.main")

class RemoteFileInput(BaseModel):
    remote_path: str = Field(description="Remote file path, e.g., '/path/to/file'")
    content: str = Field(description="File content to write at the remote path")
    mode: int = Field(default=None, description="Optional file mode/permissions, e.g., 0o755")

class LocalTrainerInput(BaseModel):
    file_path: str = Field(description="Local path to the CSV file for training")
    target_column: str = Field(description="Column name the model should predict")

class DockerCommandInput(BaseModel):
    command: str = Field(description="The Docker CLI arguments to run (everything after 'docker'). Examples: 'ps -a', 'pull nginx:latest', 'logs abc123', 'stop mycontainer'")

class ShellCommandInput(BaseModel):
    command: str = Field(description="The Linux shell command to run on the remote server. Example: 'ls /var/log', 'cat /etc/os-release'")

class AWSCommandInput(BaseModel):
    command: str = Field(description="AWS CLI arguments (everything after 'aws'). Example: 's3 ls', 'ec2 describe-instances --output table'")

class KubectlCommandInputSchema(BaseModel):
    command: str = Field(description="kubectl arguments (everything after 'kubectl'). Example: 'get pods', 'apply -f deploy.yml'")

class PowerShellCommandInput(BaseModel):
    command: str = Field(description="PowerShell command to run on the local Windows host. Example: '(Get-ChildItem D:\\).Count', 'Get-Process', 'Get-Disk'")

class TrainModelInput(BaseModel):
    file_path: Optional[str] = Field(default=None, description="Path to the CSV dataset on this machine. Omit to use the default 50_startup.csv.")
    target_column: Optional[str] = Field(default=None, description="Column to predict. Omit to use the default 'Profit'.")

class EmailNotificationInput(BaseModel):
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Email body text")

class SMSNotificationInput(BaseModel):
    message: str = Field(description="SMS message text")

class TelegramNotificationInput(BaseModel):
    message: str = Field(description="Telegram message text")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

fastapi_app = FastAPI(title="SYNAPSE Control Plane")
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=[FRONTEND_URL])
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

linux_agent = LinuxAgent()
docker_agent = DockerAgent()
kubectl_agent = LocalKubectlAgent()
powershell_agent = LocalPowerShellAgent()
aws_agent = AWSAgent()
training_agent = TrainingAgent()
notification_agent = NotificationAgent()

tools = [
    Tool(name="RunShellCommand", func=linux_agent.run_command,
         args_schema=ShellCommandInput,
         description="Run a single Linux shell command on the remote server via SSH."),
    StructuredTool.from_function(
        name="CreateRemoteFile", func=linux_agent.create_file,
        args_schema=RemoteFileInput,
        description="Create a file with specific content at a given remote path."),
    Tool(name="RunDockerCommand", func=docker_agent.run_command,
         args_schema=DockerCommandInput,
         description="Run a Docker CLI command on the local host. Docker Desktop must be installed and running."),
    Tool(name="RunKubectlCommand", func=kubectl_agent.run_command,
         args_schema=KubectlCommandInputSchema,
         description="Run a kubectl command on the local host. Kubernetes context must be configured on the host."),
    Tool(name="RunPowerShellCommand", func=powershell_agent.run_command,
         args_schema=PowerShellCommandInput,
         description="Run a PowerShell command on the local Windows host. Use for file system queries, disk usage, process listing, and Windows administration tasks."),
    Tool(name="RunAWSCommand", func=aws_agent.run_cli,
         args_schema=AWSCommandInput,
         description="Execute any AWS CLI command. Pass everything after 'aws'."),
    StructuredTool.from_function(
        name="TrainStartupModel", func=training_agent.train_startup_model,
        args_schema=TrainModelInput,
        description="Train the ML model on a CSV dataset. Omit arguments to use the default 50_startup.csv / Profit target."),
    StructuredTool.from_function(
        name="SendEmailNotification", func=notification_agent.notify_by_email,
        args_schema=EmailNotificationInput,
        description="Send an email notification. Requires subject and body."),
    Tool(name="SendSMSNotification", func=notification_agent.notify_by_sms,
         args_schema=SMSNotificationInput,
         description="Send an SMS notification. Requires message text."),
    Tool(name="SendTelegramNotification", func=notification_agent.notify_by_telegram,
         args_schema=TelegramNotificationInput,
         description="Send a Telegram notification. Requires message text."),
    github_actions_tool,
]

router = ModelRouter()
# Trigger provider detection (sets current_provider; the streaming path uses
# router.get_clients_ordered() directly for explicit per-call failover).
router.get_llm()
logger.info(f"SYNAPSE started. LLM provider: {router.current_provider}")

docker_err = docker_agent.detect()
if docker_err:
    logger.warning("Docker not available: %s", docker_err)
kubectl_err = kubectl_agent.detect()
if kubectl_err:
    logger.warning("kubectl not available: %s", kubectl_err)
powershell_err = powershell_agent.detect()
if powershell_err:
    logger.warning("PowerShell not available: %s", powershell_err)

planner = Planner(router=router, tool_names=[t.name for t in tools])

@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")
    await sio.emit("provider_update", {"provider": router.current_provider}, to=sid)

@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")


def _event_payload(request_id: str = None, **data):
    if request_id:
        data["request_id"] = request_id
    return data


async def _stream_one_provider(client, sid, session_id, query, system_prompt, request_id):
    """Stream a single ReAct attempt against one provider. Raises on rate-limit
    so the caller can fail over; other exceptions also propagate."""
    agent = create_react_agent(client, tools, state_modifier=system_prompt)
    full_response: list[str] = []
    async for event in agent.astream_events(
        {"messages": [{"role": "user", "content": query}]}, version="v2",
    ):
        kind = event["event"]
        if kind == "on_chat_model_start":
            full_response = []
        elif kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                await sio.emit(
                    "token",
                    _event_payload(request_id, data=chunk.content, scope="final"),
                    to=sid,
                )
                full_response.append(chunk.content)
        elif kind == "on_tool_start":
            await sio.emit("tool_call", {
                "tool": event["name"], "status": "running",
                "input": str(event["data"].get("input", {}))[:200],
                **({"request_id": request_id} if request_id else {}),
            }, to=sid)
        elif kind == "on_tool_end":
            tool_name = event["name"]
            raw_out = event["data"].get("output", "")
            tool_output = raw_out if isinstance(raw_out, str) else (
                getattr(raw_out, "content", None) or str(raw_out)
            )
            agent_memory.add(
                session_id, role="tool", content=tool_output,
                tool_name=tool_name, tool_result_summary=tool_output[:150],
            )
            await sio.emit("tool_call", {
                "tool": tool_name, "status": "done",
                "output": tool_output[:200],
                **({"request_id": request_id} if request_id else {}),
            }, to=sid)
    return "".join(full_response)


async def _run_single_react(sid, session_id, query, session_context, request_id):
    system_prompt = build_prompt(session_context=session_context)
    clients = router.get_clients_ordered()
    last_exc: BaseException | None = None
    for provider, client in clients:
        try:
            if hasattr(router, "mark_current"):
                router.mark_current(provider)
            await sio.emit(
                "provider_update",
                _event_payload(request_id, provider=provider, status="active"),
                to=sid,
            )
            final = await _stream_one_provider(
                client, sid, session_id, query, system_prompt, request_id
            )
            agent_memory.add(session_id, role="agent", content=final[:300])
            await sio.emit("command_output", _event_payload(request_id, data=final), to=sid)
            return
        except Exception as e:
            if is_rate_limit_error(e):
                logger.warning(
                    f"single-ReAct: {provider} rate-limited; failing over"
                )
                await sio.emit(
                    "provider_update",
                    _event_payload(request_id, provider=provider, status="rate_limited"),
                    to=sid,
                )
                last_exc = e
                continue
            logger.error(f"Agent error sid={sid}: {e}")
            await sio.emit(
                "command_output",
                _event_payload(request_id, data=f"Error: {e}"),
                to=sid,
            )
            return
    msg = f"All LLM providers rate-limited. Last error: {last_exc}"
    logger.error(msg)
    await sio.emit("command_output", _event_payload(request_id, data=f"Error: {msg}"), to=sid)


@sio.on("execute_natural_command")
async def handle_command(sid, data):
    data = data or {}
    query = data.get("command", "").strip()
    if not query:
        return
    request_id = str(data.get("request_id") or uuid.uuid4())
    session_id = sid

    agent_memory.add(session_id, role="user", content=query)
    session_context = agent_memory.get_context(session_id)

    if not needs_planning(query):
        await _run_single_react(sid, session_id, query, session_context, request_id)
        return

    plan = planner.plan(query, session_context)
    if plan is None:
        logger.warning("Planner failed; falling back to single-ReAct")
        await _run_single_react(sid, session_id, query, session_context, request_id)
        return

    await sio.emit("plan_generated", _event_payload(request_id, plan=plan.model_dump()), to=sid)
    executor = Executor(
        router=router, tools=tools, memory=agent_memory,
        sio=sio, sid=sid, planner=planner, request_id=request_id,
    )
    try:
        results = await executor.run_plan(plan, session_id)
        final_plan = executor.final_plan or plan
        final = compose_final_answer(final_plan, results)
        agent_memory.add(session_id, role="agent", content=final[:300])
        await sio.emit("command_output", _event_payload(request_id, data=final), to=sid)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Executor error sid={sid}: {error_msg}")
        await sio.emit(
            "command_output",
            _event_payload(request_id, data=f"Error: {error_msg}"),
            to=sid,
        )
