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

## 2026-11-24 — Ambiguous writes and reviewed restoration (draft PR #87)

An authenticated GET may update both independent controls after an uncertain write when the observed global revision has advanced past the attempted CAS. Report the current registration without attributing it to the original click. An unchanged revision leaves open the possibility of a delayed write, so keep the old controls locked. Never replay the mutation. Render migration choices from the same accepted state as the controls. Route a user-confirmed restoration through the existing owner-bound, single-use issue/consume protocol. The ordinary changes API continues to reject resurrection.
