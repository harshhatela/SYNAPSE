import os
import posixpath
import logging
import time
import paramiko
from command_policy import enforce_command_policy
from tool_schemas import LinuxOutput, ToolOutput


class LinuxAgent:
    """A robust agent for running commands and managing files on a remote server via SSH."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

    def _get_ssh_client(self):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        if os.getenv("SSH_ALLOW_UNKNOWN_HOSTS", "false").lower() == "true":
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        else:
            client.set_missing_host_key_policy(paramiko.RejectPolicy())

        hostname = os.getenv("SSH_HOST")
        username = os.getenv("SSH_USERNAME") or os.getenv("SSH_USER")
        password = os.getenv("SSH_PASSWORD")
        key_path = os.getenv("SSH_KEY_PATH")
        if key_path:
            key_path = os.path.expanduser(key_path)
        if not hostname or not username:
            raise ValueError("SSH_HOST and SSH_USERNAME (or SSH_USER) must be set")
        if not password and not key_path:
            raise ValueError("Set SSH_PASSWORD or SSH_KEY_PATH for SSH authentication")

        auth_is_explicit = bool(password or key_path)
        client.connect(
            hostname=hostname,
            username=username,
            password=password or None,
            key_filename=key_path or None,
            port=int(os.getenv("SSH_PORT", 22)),
            look_for_keys=not auth_is_explicit,
            allow_agent=not auth_is_explicit,
            timeout=15,
        )
        return client

    def run_command(self, command: str) -> str:
        """Runs a single shell command on the remote server."""
        start = time.monotonic()
        command, policy_error = enforce_command_policy(command, "shell")
        if policy_error:
            return LinuxOutput(
                success=False, summary="Command blocked by safety policy",
                stdout="", stderr=policy_error, exit_code=-1,
                execution_time_ms=0, error=policy_error,
            ).model_dump_json()

        client = None
        try:
            client = self._get_ssh_client()
            stdin, stdout, stderr = client.exec_command(command)
            exit_code = stdout.channel.recv_exit_status()
            out = stdout.read().decode("utf-8").strip()
            err = stderr.read().decode("utf-8").strip()
            elapsed = (time.monotonic() - start) * 1000
            if exit_code != 0:
                self.logger.error("Command failed (%s): %s", exit_code, err)
                return LinuxOutput(
                    success=False, summary=f"Command failed (exit {exit_code})",
                    stdout=out, stderr=err, exit_code=exit_code,
                    execution_time_ms=elapsed, error=err,
                ).model_dump_json()
            self.logger.debug("Command succeeded: %s", out or "no output")
            return LinuxOutput(
                success=True, summary="Command executed successfully",
                stdout=out or "Command executed successfully.",
                exit_code=exit_code, execution_time_ms=elapsed,
            ).model_dump_json()
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            self.logger.error("SSH command failed before completion: %s", e)
            return LinuxOutput(
                success=False, summary="SSH command failed",
                stdout="", stderr=str(e), exit_code=-1,
                execution_time_ms=elapsed, error=str(e),
            ).model_dump_json()
        finally:
            if client is not None:
                client.close()

    def create_file(self, remote_path: str, content: str, mode: int = None) -> str:
        """Creates a file with specific content on the remote server using SFTP.
        Ensures parent directories exist, expands '~', and optionally sets file mode."""
        client = None
        sftp = None
        try:
            client = self._get_ssh_client()
            sftp = client.open_sftp()

            # Expand ~ to home directory
            if remote_path.startswith('~'):
                stdin, stdout, _ = client.exec_command('echo $HOME')
                home = stdout.read().decode().strip()
                remote_path = remote_path.replace('~', home, 1)

            # Ensure parent directories exist
            dirname = posixpath.dirname(remote_path)
            if dirname:
                self._ensure_remote_dir(sftp, dirname)

            # Write file
            with sftp.open(remote_path, 'w') as f:
                f.write(content)

            # Set permissions if requested
            if mode is not None:
                sftp.chmod(remote_path, mode)

            self.logger.debug("File created at %s", remote_path)
            return ToolOutput(
                success=True,
                tool_name="linux_file",
                summary=f"File created successfully at {remote_path}.",
            ).model_dump_json()
        except Exception as e:
            self.logger.error("Failed to create file %s: %s", remote_path, e)
            return ToolOutput(
                success=False,
                tool_name="linux_file",
                summary=f"Error creating file at {remote_path}",
                error=str(e),
            ).model_dump_json()
        finally:
            if sftp is not None:
                try:
                    sftp.close()
                except Exception:
                    pass
            if client is not None:
                client.close()

    def _ensure_remote_dir(self, sftp, remote_dir: str):
        """Recursively create directories on the remote server if they do not exist."""
        parts = remote_dir.split('/')
        path = ''
        for part in parts:
            if not part:
                continue
            path = f"{path}/{part}"
            try:
                sftp.stat(path)
            except FileNotFoundError:
                self.logger.debug("Creating remote directory: %s", path)
                sftp.mkdir(path)
