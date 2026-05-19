import json
from unittest.mock import MagicMock, patch
from powershell_agent import LocalPowerShellAgent


def _agent():
    return LocalPowerShellAgent(timeout=30)


def test_run_command_success():
    agent = _agent()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="42\n", stderr="")
        result = json.loads(agent.run_command("(Get-ChildItem D:\\).Count"))
    assert result["success"] is True
    assert result["stdout"] == "42"
    assert result["exit_code"] == 0


def test_run_command_failure():
    agent = _agent()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Access denied"
        )
        result = json.loads(agent.run_command("Remove-Item C:\\Windows\\System32"))
    assert result["success"] is False
    assert result["stderr"] == "Access denied"
    assert result["exit_code"] == 1


def test_run_command_timeout():
    import subprocess
    agent = _agent()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ps", timeout=30)):
        result = json.loads(agent.run_command("Start-Sleep 999"))
    assert result["success"] is False
    assert result["exit_code"] == -1
    assert "timeout" in result["summary"].lower() or "Timeout" in result["stderr"]


def test_run_command_not_found():
    agent = _agent()
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = json.loads(agent.run_command("Get-Process"))
    assert result["success"] is False
    assert result["exit_code"] == -1
    assert "not found" in result["summary"].lower()


def test_detect_success():
    agent = _agent()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="5.1.19041.4648", stderr="")
        err = agent.detect()
    assert err is None


def test_detect_not_found():
    agent = _agent()
    with patch("subprocess.run", side_effect=FileNotFoundError):
        err = agent.detect()
    assert err is not None
    assert "not found" in err.lower()


def test_detect_failure_returncode():
    agent = _agent()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Oops")
        err = agent.detect()
    assert err is not None
    assert "failed" in err.lower()
