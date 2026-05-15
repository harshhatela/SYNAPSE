# Open Issues

## High Priority
- [ ] No SSH connection pooling — Paramiko opens a new connection per tool call. High latency for multi-tool workflows.
- [ ] No approval gate for destructive commands — currently prompt-level only, not enforced in code.

## Medium Priority
- [ ] No audit log for prompt → tool call → output chain.
- [ ] agent_executor created per request in memory-wired path — could be expensive at scale.

## Low Priority
- [ ] CORS hardcoded to localhost:5173 — needs env-var for production.
