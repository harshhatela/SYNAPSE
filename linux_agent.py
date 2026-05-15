import os
import posixpath
import logging
import time
import paramiko
from tool_schemas import LinuxOutput


class LinuxAgent:
    """A robust agent for running commands and managing files on a remote server via SSH."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

    def _get_ssh_client(self):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=os.getenv("SSH_HOST"),
            username=os.getenv("SSH_USERNAME"),
            password=os.getenv("SSH_PASSWORD"),
            port=int(os.getenv("SSH_PORT", 22)),
            look_for_keys=False,
            allow_agent=False
        )
        return client

    def run_command(self, command: str) -> str:
        """Runs a single shell command on the remote server."""
        client = self._get_ssh_client()
        start = time.monotonic()
        try:
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
        finally:
            client.close()

    def create_file(self, remote_path: str, content: str, mode: int = None) -> str:
        """Creates a file with specific content on the remote server using SFTP.
        Ensures parent directories exist, expands '~', and optionally sets file mode."""
        client = self._get_ssh_client()
        try:
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
            return f"File created successfully at {remote_path}."
        except Exception as e:
            self.logger.error("Failed to create file %s: %s", remote_path, e)
            return f"Error creating file at {remote_path}: {e}"
        finally:
            try:
                sftp.close()
            except Exception:
                pass
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
