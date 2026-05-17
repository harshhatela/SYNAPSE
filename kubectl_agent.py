import json
import shlex
import sys
import logging
import subprocess
from typing import Optional

from tool_schemas import KubectlOutput

logger = logging.getLogger(__name__)


class LocalKubectlAgent:
    """Runs `kubectl <command>` on the local host via subprocess."""

    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def detect(self) -> Optional[str]:
        try:
            cp = subprocess.run(
                ["kubectl", "version", "--client", "--output=yaml"],
                capture_output=True, text=True, timeout=5,
            )
            if cp.returncode != 0:
                return f"kubectl client version exited {cp.returncode}"
            return None
        except FileNotFoundError:
            return "kubectl binary not found on PATH"
        except Exception as e:
            return f"kubectl detect failed: {e}"

    def run_command(self, command: str) -> str:
        argv = ["kubectl", *shlex.split(command, posix=(sys.platform != "win32"))]
        try:
            cp = subprocess.run(
                argv, capture_output=True, text=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return KubectlOutput(
                success=False,
                summary=f"kubectl {command}: timed out after {self.timeout}s",
                stdout="", stderr="timeout", exit_code=-1,
                error="timeout",
            ).model_dump_json()
        except FileNotFoundError:
            return KubectlOutput(
                success=False,
                summary="kubectl binary not found on PATH",
                stdout="", stderr="", exit_code=-1,
                error="not_found",
            ).model_dump_json()
        except Exception as e:
            return KubectlOutput(
                success=False,
                summary=f"kubectl {command}: {e}",
                stdout="", stderr=str(e), exit_code=-1,
                error=str(e),
            ).model_dump_json()

        stdout = (cp.stdout or "").strip()
        stderr = (cp.stderr or "").strip()
        ok = cp.returncode == 0
        return KubectlOutput(
            success=ok,
            summary=(f"kubectl {command}: ok" if ok
                     else f"kubectl {command}: exit {cp.returncode}"),
            stdout=stdout, stderr=stderr, exit_code=cp.returncode,
            error=None if ok else stderr,
        ).model_dump_json()
