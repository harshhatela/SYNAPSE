import subprocess
import os
import shlex

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
            return result.stdout.strip() if result.stdout else "Command executed successfully with no output."
        
        except subprocess.CalledProcessError as e:
            # Provide a more informative error message
            return f"Error executing command: '{' '.join(e.cmd)}'. Stderr: {e.stderr.strip()}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"