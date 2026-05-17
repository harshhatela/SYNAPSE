import json
import subprocess
from unittest.mock import patch, MagicMock
from kubectl_agent import LocalKubectlAgent


def _cp(stdout="", stderr="", rc=0):
    m = MagicMock()
    m.stdout = stdout; m.stderr = stderr; m.returncode = rc
    return m


def test_kubectl_success():
    a = LocalKubectlAgent()
    with patch("kubectl_agent.subprocess.run", return_value=_cp(stdout="pods\n")):
        out = json.loads(a.run_command("get pods"))
    assert out["success"] is True
    assert out["stdout"] == "pods"


def test_kubectl_nonzero():
    a = LocalKubectlAgent()
    with patch("kubectl_agent.subprocess.run", return_value=_cp(stderr="nope", rc=1)):
        out = json.loads(a.run_command("apply -f bad.yml"))
    assert out["success"] is False
    assert out["exit_code"] == 1


def test_kubectl_timeout():
    a = LocalKubectlAgent(timeout=1)
    with patch("kubectl_agent.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="kubectl", timeout=1)):
        out = json.loads(a.run_command("get pods"))
    assert out["success"] is False
    assert "timed out" in out["summary"].lower()


def test_kubectl_not_found():
    a = LocalKubectlAgent()
    with patch("kubectl_agent.subprocess.run", side_effect=FileNotFoundError()):
        out = json.loads(a.run_command("get pods"))
    assert out["success"] is False
    assert "kubectl" in out["summary"].lower()
