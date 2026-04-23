from linux_agent import LinuxAgent


class DockerTool:
    """A tool to execute Docker commands on the remote server."""
    def __init__(self):
        # Reuse the LinuxAgent to execute commands via SSH
        self.ssh_tool = LinuxAgent()

    def list_containers(self, args: str = "") -> str:
        """
        Lists Docker containers. Accepts optional arguments like '-a' to show all.
        Example: list_containers(args="-a")
        """
        # Use the correct LinuxAgent method name
        return self.ssh_tool.run_command(f"docker ps {args}")

    def get_logs(self, container_id: str) -> str:
        """
        Fetches the logs for a specific Docker container by its ID.
        Example: get_logs(container_id="a1b2c3d4e5f6")
        """
        return self.ssh_tool.run_command(f"docker logs {container_id}")

    def run_command(self, command: str) -> str:
        """
        Runs any generic Docker command.
        Example: run_command(command="pull nginx:latest")
        """
        return self.ssh_tool.run_command(f"docker {command}")
