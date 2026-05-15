import subprocess
import os
import shlex
import json
from tool_schemas import AWSOutput

class AWSAgent:
    """A tool to interact with AWS by executing AWS CLI commands."""
    def __init__(self):
        self.region = os.getenv("AWS_DEFAULT_REGION")
        if not self.region:
            raise ValueError("AWS_DEFAULT_REGION not set in .env file.")

    def run_cli(self, command: str) -> str:
        """
        Executes an AWS CLI command and returns the output.
        The input command should be the arguments that follow 'aws', 
        e.g., 's3 ls' or 'ec2 describe-instances'.
        """
        try:
            # Split the command string safely to handle quotes and spaces
            command_parts = shlex.split(command)
            
            # --- THE FIX: Make the command construction resilient ---
            # If the agent mistakenly includes "aws", we remove it to prevent duplication.
            if command_parts and command_parts[0] == "aws":
                command_parts = command_parts[1:]

            # Build the final, correct command list
            final_command_list = ["aws"] + command_parts
            
            # Add the region if it's not already specified in the command
            if "--region" not in final_command_list:
                final_command_list.extend(["--region", self.region])

            # Execute the command
            result = subprocess.run(
                final_command_list,
                capture_output=True,
                text=True,
                check=True # This will raise an exception for non-zero exit codes
            )
            raw_stdout = result.stdout.strip() if result.stdout else ""
            parsed = None
            try:
                parsed = json.loads(raw_stdout)
            except Exception:
                pass
            return AWSOutput(
                success=True, summary="AWS command succeeded",
                raw_output=raw_stdout or "Command executed successfully with no output.",
                parsed_data=parsed,
            ).model_dump_json()

        except subprocess.CalledProcessError as e:
            raw_stderr = e.stderr.strip() if e.stderr else f"Error executing command: '{' '.join(e.cmd)}'"
            return AWSOutput(
                success=False, summary="AWS command failed",
                raw_output=raw_stderr, error=raw_stderr,
            ).model_dump_json()
        except Exception as e:
            raw_stderr = str(e)
            return AWSOutput(
                success=False, summary="AWS command failed",
                raw_output=raw_stderr, error=raw_stderr,
            ).model_dump_json()