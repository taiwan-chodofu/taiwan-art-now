# AI collaboration decision log

## 2026-11-22 — GitHub-based handoff
Status: Proposed; subject to PR review.
Decision: Use `AGENTS.md` for common agent rules, `CLAUDE.md` for Claude Code startup, `CURRENT.md` for current handoff, this file for durable decisions, GitHub Issues for tasks, and PRs for review.
Rationale: Both agents can retrieve versioned context without assuming access to each other's chat history.
Tradeoffs: Agents must explicitly update and commit handoff notes; no automatic conversation transcript synchronization. Never store private information or secrets in this public repository.

## 2026-11-22 — Improvement priority
Status: Proposed; not an implementation authorization.
Decision: Prioritize subscriber security and preview access, followed by archive/CI data integrity, then stable exhibition IDs and link migration, before extensive UI redesign.
Rationale: Protect user data and continuity before structural UI changes.
