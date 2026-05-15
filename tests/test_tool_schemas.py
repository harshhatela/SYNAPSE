from tool_schemas import LinuxOutput, DockerOutput, AWSOutput, ToolOutput

def test_linux_output_serializes_to_json():
    out = LinuxOutput(success=True, summary="done", stdout="hello", exit_code=0, execution_time_ms=12.3)
    data = out.model_dump()
    assert data["tool_name"] == "linux"
    assert data["success"] is True
    assert data["stdout"] == "hello"

def test_tool_output_captures_error():
    out = LinuxOutput(success=False, summary="failed", stdout="", exit_code=1,
                      execution_time_ms=5.0, error="permission denied")
    assert out.error == "permission denied"
    assert out.success is False

def test_aws_output_json_roundtrip():
    out = AWSOutput(success=True, summary="listed buckets", raw_output='{"Buckets": []}')
    json_str = out.model_dump_json()
    assert '"tool_name":"aws"' in json_str
