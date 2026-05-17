import json
from unittest.mock import patch, MagicMock
import subprocess
import pytest
from docker_agent import LocalDockerAgent


def _fake_completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    cp = MagicMock()
    cp.stdout = stdout
    cp.stderr = stderr
    cp.returncode = returncode
    return cp


def test_run_command_success():
    agent = LocalDockerAgent()
    with patch("docker_agent.subprocess.run", return_value=_fake_completed(stdout="hello\n")):
        out = json.loads(agent.run_command("ps"))
    assert out["success"] is True
    assert out["stdout"] == "hello"
    assert out["exit_code"] == 0


def test_run_command_nonzero_exit():
    agent = LocalDockerAgent()
    with patch("docker_agent.subprocess.run",
               return_value=_fake_completed(stderr="boom", returncode=1)):
        out = json.loads(agent.run_command("foo"))
    assert out["success"] is False
    assert "boom" in (out.get("stderr") or "")
    assert out["exit_code"] == 1


def test_run_command_timeout():
    agent = LocalDockerAgent(timeout=1)
    with patch("docker_agent.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="docker ps", timeout=1)):
        out = json.loads(agent.run_command("ps"))
    assert out["success"] is False
    assert "timed out" in out["summary"].lower()


def test_run_command_docker_not_found():
    agent = LocalDockerAgent()
    with patch("docker_agent.subprocess.run",
               side_effect=FileNotFoundError("docker not on PATH")):
        out = json.loads(agent.run_command("ps"))
    assert out["success"] is False
    assert "docker" in out["summary"].lower()
