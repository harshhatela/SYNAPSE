import subprocess
import os
import shlex
import json
from command_policy import enforce_command_policy
from tool_schemas import AWSOutput

class AWSAgent:
    """A tool to interact with AWS by executing AWS CLI commands."""
    def __init__(self, timeout: int = 300):
        self.region = os.getenv("AWS_DEFAULT_REGION")
        self.timeout = timeout

    def run_cli(self, command: str) -> str:
        if not self.region:
            return AWSOutput(
                success=False, summary="AWS not configured",
                raw_output="AWS_DEFAULT_REGION not set in environment.",
                error="AWS_DEFAULT_REGION not set",
            ).model_dump_json()
        command, policy_error = enforce_command_policy(command, "aws")
        if policy_error:
            return AWSOutput(
                success=False,
                summary="AWS command blocked by safety policy",
                raw_output="",
                error=policy_error,
            ).model_dump_json()
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

            # Force the env-configured region. The LLM frequently hardcodes
            # `--region us-east-1` in commands; strip any LLM-supplied --region
            # and inject AWS_DEFAULT_REGION so the user's .env is authoritative.
            cleaned: list[str] = []
            i = 0
            while i < len(final_command_list):
                tok = final_command_list[i]
                if tok == "--region":
                    i += 2  # skip flag + its value
                    continue
                if tok.startswith("--region="):
                    i += 1
                    continue
                cleaned.append(tok)
                i += 1
            final_command_list = cleaned + ["--region", self.region]

            # Execute the command (bounded so `aws ec2 wait ...` cannot hang forever).
            result = subprocess.run(
                final_command_list,
                capture_output=True,
                text=True,
                check=True,
                timeout=self.timeout,
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

        except subprocess.TimeoutExpired:
            return AWSOutput(
                success=False, summary=f"AWS command timed out after {self.timeout}s",
                raw_output="", error="timeout",
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
