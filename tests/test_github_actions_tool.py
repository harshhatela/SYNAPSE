import pytest
from unittest.mock import patch, MagicMock
from tool_schemas import GitHubActionsOutput
import json

def test_missing_github_token_raises():
    import os
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("GITHUB_TOKEN", None)
        from github_actions_tool import _headers
        with pytest.raises(ValueError, match="GITHUB_TOKEN not set"):
            _headers()

def test_list_action_returns_output():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "workflow_runs": [
            {"id": 1, "status": "completed", "conclusion": "success",
             "created_at": "2026-05-15T10:00:00Z", "html_url": "https://github.com/x/y/actions/runs/1"}
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        with patch.dict("os.environ", {"GITHUB_TOKEN": "test_token"}):
            from github_actions_tool import _list_runs
            result = _list_runs("owner", "repo", "deploy.yml")
            parsed = json.loads(result)
            assert parsed["success"] is True
            assert len(parsed["jobs"]) == 1
