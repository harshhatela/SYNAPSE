from command_policy import enforce_command_policy, is_destructive_command


def test_destructive_shell_command_requires_confirmation():
    clean, error = enforce_command_policy("rm -rf /tmp/app", "shell")
    assert clean == "rm -rf /tmp/app"
    assert error is not None


def test_confirmation_prefix_is_stripped():
    clean, error = enforce_command_policy("CONFIRMED: rm -rf /tmp/app", "shell")
    assert clean == "rm -rf /tmp/app"
    assert error is None


def test_docker_and_kubectl_destructive_patterns():
    assert is_destructive_command("system prune -af", "docker") is True
    assert is_destructive_command("delete deployment web", "kubectl") is True
    assert is_destructive_command("ps -a", "docker") is False
