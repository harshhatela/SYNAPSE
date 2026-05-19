import logging
import subprocess
from typing import Optional

from command_policy import enforce_command_policy
from tool_schemas import PowerShellOutput

logger = logging.getLogger(__name__)


class LocalPowerShellAgent:
    """Runs PowerShell commands on the local Windows host via subprocess."""

    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def detect(self) -> Optional[str]:
        try:
            cp = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Write-Output $PSVersionTable.PSVersion.ToString()"],
                capture_output=True, text=True, timeout=10,
            )
            if cp.returncode != 0:
                return f"PowerShell check failed: {cp.stderr.strip()}"
            return None
        except FileNotFoundError:
            return "PowerShell not found on PATH"
        except Exception as e:
            return f"PowerShell detect failed: {e}"

    def run_command(self, command: str) -> str:
        command, policy_error = enforce_command_policy(command, "powershell")
        if policy_error:
            return PowerShellOutput(
                success=False,
                summary="PowerShell command blocked by safety policy",
                stdout="",
                stderr=policy_error,
                exit_code=-1,
                error=policy_error,
            ).model_dump_json()

        try:
            cp = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, text=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return PowerShellOutput(
                success=False,
                summary=f"PowerShell command timed out after {self.timeout}s",
                stdout="", stderr=f"Timeout after {self.timeout}s", exit_code=-1,
                error="timeout",
            ).model_dump_json()
        except FileNotFoundError:
            return PowerShellOutput(
                success=False,
                summary="PowerShell not found on PATH",
                stdout="", stderr="", exit_code=-1,
                error="not_found",
            ).model_dump_json()
        except Exception as e:
            return PowerShellOutput(
                success=False,
                summary=str(e),
                stdout="", stderr=str(e), exit_code=-1,
                error=str(e),
            ).model_dump_json()

        stdout = (cp.stdout or "").strip()
        stderr = (cp.stderr or "").strip()
        ok = cp.returncode == 0
        return PowerShellOutput(
            success=ok,
            summary=stdout[:200] if ok else (stderr[:200] or f"exit {cp.returncode}"),
            stdout=stdout,
            stderr=stderr or None,
            exit_code=cp.returncode,
            error=None if ok else (stderr or f"exit {cp.returncode}"),
        ).model_dump_json()
