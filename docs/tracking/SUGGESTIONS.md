# Improvement Suggestions

## Architecture
- Move long-running tool calls to a worker queue (Celery or asyncio.Queue) for better concurrency.
- Add SSH session pooling to reduce per-call latency.
- Persist AgentMemory to SQLite for cross-process session continuity.

## Features
- Add streaming partial tool outputs (not just LLM tokens) over Socket.IO.
- Add a ToolBadges UI component showing which tools were called in each response.
- Add AgentWatch integration for observability (self-dogfooding).

## Developer Experience
- Add a `--dry-run` flag to preview tool calls before execution.
- Add a replay mode — replay a past session from logs.
