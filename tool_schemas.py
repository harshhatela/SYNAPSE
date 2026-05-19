from pydantic import BaseModel, Field
from typing import Optional, Literal


class LinuxInput(BaseModel):
    command: str
    working_dir: Optional[str] = "/tmp"
    timeout_seconds: int = 30

class DockerInput(BaseModel):
    action: Literal["build", "run", "stop", "logs", "ps", "pull", "exec"]
    image: Optional[str] = None
    container_id: Optional[str] = None
    command: Optional[str] = None
    ports: Optional[dict] = None
    env_vars: Optional[dict] = None
    detach: bool = True

class AWSInput(BaseModel):
    action: str
    region: str = "us-east-1"
    output_format: Literal["json", "text", "table"] = "json"

class GitHubActionsInput(BaseModel):
    owner: str
    repo: str
    workflow_id: str
    ref: str = "main"
    inputs: Optional[dict] = None
    action: Literal["trigger", "status", "list"] = "trigger"
    run_id: Optional[int] = None

class TelegramInput(BaseModel):
    message: str
    chat_id: Optional[str] = None
    parse_mode: Literal["Markdown", "HTML", "plain"] = "Markdown"

class EmailInput(BaseModel):
    to: str
    subject: str
    body: str

class SMSInput(BaseModel):
    to: str
    message: str

class MLTrainInput(BaseModel):
    file_path: str
    target_column: str
    test_size: float = 0.2
    n_estimators: int = 100


class ToolOutput(BaseModel):
    success: bool
    tool_name: str
    summary: str
    error: Optional[str] = None

class LinuxOutput(ToolOutput):
    tool_name: str = "linux"
    stdout: str
    stderr: Optional[str] = None
    exit_code: int
    execution_time_ms: float

class DockerOutput(ToolOutput):
    tool_name: str = "docker"
    container_id: Optional[str] = None
    logs: Optional[str] = None
    running_containers: Optional[list] = None

class AWSOutput(ToolOutput):
    tool_name: str = "aws"
    raw_output: str
    parsed_data: Optional[dict] = None

class GitHubActionsOutput(ToolOutput):
    tool_name: str = "github_actions"
    run_id: Optional[int] = None
    run_url: Optional[str] = None
    status: Optional[str] = None
    conclusion: Optional[str] = None
    workflow_name: Optional[str] = None
    jobs: Optional[list] = None

class TelegramOutput(ToolOutput):
    tool_name: str = "telegram"
    message_id: Optional[int] = None

class EmailOutput(ToolOutput):
    tool_name: str = "email"
    message_id: Optional[str] = None

class SMSOutput(ToolOutput):
    tool_name: str = "sms"
    message_sid: Optional[str] = None

class MLTrainOutput(ToolOutput):
    tool_name: str = "ml_train"
    model_path: Optional[str] = None
    metrics: Optional[dict] = None


# ─── Kubernetes ──────────────────────────────────────────

class KubectlCommandInput(BaseModel):
    command: str  # kubectl arguments, e.g. "get pods", "apply -f deploy.yml"

class KubectlOutput(ToolOutput):
    tool_name: str = "kubectl"
    stdout: str
    stderr: Optional[str] = None
    exit_code: int


# ─── PowerShell ───────────────────────────────────────────

class PowerShellOutput(ToolOutput):
    tool_name: str = "powershell"
    stdout: str
    stderr: Optional[str] = None
    exit_code: int


# ─── Planner / Executor ─────────────────────────────────

class PlanStep(BaseModel):
    step_id: int
    description: str
    intended_tool: str
    success_criteria: str

class Plan(BaseModel):
    steps: list[PlanStep]
    reasoning: str

class StepResult(BaseModel):
    step_id: int
    status: Literal["done", "failed"]
    summary: str
    tool_outputs: list[dict] = Field(default_factory=list)
