from dotenv import load_dotenv
load_dotenv()
import logging
logging.basicConfig(level=logging.DEBUG)

import asyncio
import os
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.tools import Tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

# Import all our specialized agents
from linux_agent import LinuxAgent
from docker_agent import DockerTool as DockerAgent
from aws_agent import AWSAgent
from training_agent import TrainingAgent
from notification_agent import NotificationAgent

# Define the input schema for CreateRemoteFile
class RemoteFileInput(BaseModel):
    remote_path: str = Field(description="Remote file path, e.g., '/path/to/file'")
    content: str = Field(description="File content to write at the remote path")
    mode: int = Field(default=None, description="Optional file mode/permissions, e.g., 0o755")

# Define the input schema for the TrainLocalModel tool
class LocalTrainerInput(BaseModel):
    file_path: str = Field(description="The local file path to the CSV file to be used for training, e.g., '/path/to/file.csv'.")
    target_column: str = Field(description="The name of the column in the CSV file that the model should predict.")

# Initialize FastAPI app & Socket.IO
fastapi_app = FastAPI()
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

# Instantiate all tool providers
linux_agent = LinuxAgent()
docker_agent = DockerAgent()
aws_agent = AWSAgent()
training_agent = TrainingAgent()
notification_agent = NotificationAgent()

# Create a clear, flexible toolbelt of micro-tasks
tools = [
    Tool(
        name="RunShellCommand",
        func=linux_agent.run_command,
        description="Use to run a single, general-purpose Linux shell command on a remote server."
    ),
    Tool(
        name="CreateRemoteFile",
        func=linux_agent.create_file,
        args_schema=RemoteFileInput,
        description="Create a file with specific content at a given path on the remote server."
    ),
    Tool(
        name="RunDockerCommand",
        func=docker_agent.run_command,
        description="Use to run a single Docker CLI command on the remote server via shell."
    ),
    Tool(
        name="RunAWSCommand",
        func=aws_agent.run_cli,
        description="Use for executing any AWS CLI command."
    ),
    Tool(
    name="TrainStartupModel",
    func=training_agent.train_startup_model,
    description="Use this specific tool to train the machine learning model for the 50_startup.csv dataset. It takes no arguments."
    ),
    Tool(
        name="SendEmailNotification",
        func=notification_agent.notify_by_email,
        description="Send an email notification with a subject and body when a task is finished."
    ),
    Tool(
        name="SendSMSNotification",
        func=notification_agent.notify_by_sms,
        description="Send an SMS notification when a task is finished."
    ),
    Tool(
        name="SendTelegramNotification",
        func=notification_agent.notify_by_telegram,
        description="Send a Telegram notification when a task is finished."
    ),
]

# Set up the LangChain agent with langgraph
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

# Create the agent using langgraph's create_react_agent
agent_executor = create_react_agent(llm, tools)

# Define Socket.IO event handlers
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

@sio.on('execute_natural_command')
async def handle_command(sid, data):
    query = data.get('command')
    if not query:
        return
    try:
        result = await asyncio.to_thread(
            agent_executor.invoke,
            {"messages": [("human", query)]}
        )
        output = result.get('messages', [])[-1].content if result.get('messages') else 'No output from agent.'
    except Exception as e:
        output = f"An error occurred: {str(e)}"
    await sio.emit('command_output', {'data': output}, to=sid)
