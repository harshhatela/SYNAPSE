# Changelog

## 2026-05-15 / 2026-05-16
- fix: align frontend socket events with backend contract (Task 1)
- fix: run agent invoke in thread executor to unblock async event loop (Task 2)
- feat: add ModelRouter with Groq→Gemini→Cerebras→Ollama fallback (Task 3)
- feat: wire ModelRouter and streaming with astream_events (Task 4)
- feat: add ModelIndicator component (Task 5)
- chore: update requirements and .env.example (Task 6)
- feat: add Pydantic I/O schemas for all tools (Task 7)
- feat: update tools to return typed JSON output (Task 8)
- feat: add AgentMemory (Task 9)
- feat: add system prompt and wire memory into handler (Task 10)
- feat: add GitHub Actions tool (Task 11)
- fix: make TrainingAgent dataset path and target column configurable (Task 12)
- chore: remove unwired dead code modules (Task 13)
- docs: rewrite README in product-page format (Task 14)
- docs: add project tracking system (Task 15)
