import json
import shlex
import logging
import subprocess
import sys
from typing import Optional

from tool_schemas import DockerOutput

logger = logging.getLogger(__name__)


class LocalDockerAgent:
    """Runs `docker <command>` on the local host via subprocess.

    Docker Desktop (or `docker` on PATH) must be installed and running.
    No SSH involved — host-local only.
    """

    def __init__(self, timeout: int = 120):
        self.timeout = timeout
        self._detect_logged = False

    def detect(self) -> Optional[str]:
        """Returns None if docker is available, else an error string."""
        try:
            cp = subprocess.run(
                ["docker", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if cp.returncode != 0:
                return f"docker --version exited {cp.returncode}: {cp.stderr.strip()}"
            return None
        except FileNotFoundError:
            return "docker binary not found on PATH (install Docker Desktop)"
        except Exception as e:
            return f"docker detect failed: {e}"

    def run_command(self, command: str) -> str:
        """Run `docker <command>` locally. Returns JSON-serialized DockerOutput."""
        argv = ["docker", *shlex.split(command, posix=(sys.platform != "win32"))]
        try:
            cp = subprocess.run(
                argv, capture_output=True, text=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return DockerOutput(
                success=False,
                summary=f"docker {command}: timed out after {self.timeout}s",
                error="timeout",
            ).model_dump_json()
        except FileNotFoundError:
            return DockerOutput(
                success=False,
                summary="docker binary not found on PATH (install Docker Desktop)",
                error="not_found",
            ).model_dump_json()
        except Exception as e:
            return DockerOutput(
                success=False,
                summary=f"docker {command}: {e}",
                error=str(e),
            ).model_dump_json()

        stdout = (cp.stdout or "").strip()
        stderr = (cp.stderr or "").strip()
        ok = cp.returncode == 0
        payload = DockerOutput(
            success=ok,
            summary=(f"docker {command}: ok" if ok
                     else f"docker {command}: exit {cp.returncode}"),
            error=None if ok else stderr,
        ).model_dump()
        payload["stdout"] = stdout
        payload["stderr"] = stderr
        payload["exit_code"] = cp.returncode
        return json.dumps(payload)
