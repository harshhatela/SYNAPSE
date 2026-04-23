# SYNAPSE

SYNAPSE is a two-part AI agent workspace with a Python backend and a React + Vite frontend.

The backend exposes a FastAPI + Socket.IO service that coordinates specialized agents for Linux, Docker, AWS, training, and notifications. The frontend in `synapse/` provides the chat interface and connects to the backend on `http://localhost:8000`.

## Project Layout

```text
.
├── main.py              # FastAPI / Socket.IO app and agent orchestration
├── start_backend.py     # Uvicorn entry point for the backend
├── requirements.txt     # Python dependencies
├── 50_startup.csv       # Dataset used by the training agent
├── synapse/             # Vite + React frontend
│   ├── src/
│   ├── public/
│   └── package.json
```

## Backend

The backend is defined in `main.py` and starts an ASGI app that serves Socket.IO events. It uses `langgraph` with `ChatGoogleGenerativeAI` and a set of specialized tools for:

- running shell commands
- creating remote files
- running Docker commands
- running AWS CLI commands
- training a startup model from `50_startup.csv`
- sending email, SMS, and Telegram notifications

### Backend Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set the required environment variable:

   ```bash
   GEMINI_API_KEY=your_api_key_here
   ```

4. Start the backend:

   ```bash
   python start_backend.py
   ```

The backend listens on `http://0.0.0.0:8000`.

## Frontend

The frontend lives in `synapse/` and is built with React, TypeScript, Vite, and Socket.IO client support.

### Frontend Setup

1. Move into the frontend folder:

   ```bash
   cd synapse
   ```

2. Install dependencies:

   ```bash
   npm install
   ```

3. Start the development server:

   ```bash
   npm run dev
   ```

The frontend expects the backend at `http://localhost:8000`.

## Available Scripts

### Backend

- `python start_backend.py` starts the ASGI server

### Frontend

- `npm run dev` starts the Vite dev server
- `npm run build` creates a production build
- `npm run preview` previews the production build
- `npm run lint` runs ESLint

## Notes

- Local-only files such as `.env`, `.venv/`, `backend.log`, and `my-ec2-key.pem` should stay untracked.
- The frontend already has its own `.gitignore`, and the root ignore file now covers the workspace-wide Python and secret artifacts as well.