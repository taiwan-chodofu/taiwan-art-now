# Taiwan Art Now — Shared AI Collaboration Rules

This file is the shared entry point for ChatGPT, Claude Code, and other coding agents.

## Mandatory start of every session
1. Read `DATA_QUALITY_RULES.md`, `docs/ai-handoff/CURRENT.md`, and `docs/ai-handoff/DECISIONS.md`. Claude Code also reads `CLAUDE.md`.
2. Inspect local branch and working tree, fetch the latest remote state when possible, and check open Issues/PRs relevant to the task. Never assume a previous conversation reflects current code.
3. Identify the active task owner, branch and PR; avoid overwriting another agent's uncommitted or in-progress changes.
4. Inspect relevant implementation and tests. Before changes, state the plan, risks, verification and blockers. If remote state cannot be checked, say so.
5. Follow `DATA_QUALITY_RULES.md`: official exhibition sources take precedence; do not invent or machine-translate official Traditional Chinese exhibition titles.

## Mandatory end of every session
1. Update `docs/ai-handoff/CURRENT.md` on the working branch with objective, completed work, files changed, tests actually run, unresolved issues and precise next actions.
2. Record durable decisions in `docs/ai-handoff/DECISIONS.md` with date, rationale, status and tradeoffs.
3. Commit/push the handoff on the work branch and link the relevant issue/PR, or explicitly report why it could not be published.
4. Distinguish verified facts from hypotheses and pending decisions. Never claim tests passed unless executed.

## Collaboration and safety
- GitHub Issues track tasks; PRs track implementation/review. Use a separate branch/PR per bounded change; do not push directly to `main`.
- Never assume private ChatGPT or Claude conversations are synchronized; only explicitly committed handoffs are shared.
- Never commit credentials, subscriber IDs, private tokens, personal data, or private conversation transcripts.
- Do not deploy, merge, rotate credentials, or mutate production data without explicit approval.
- Preserve exhibition records, favorites/visited state, subscriber integrations and URLs unless a migration is approved.
- Add regression tests for subscriber authorization, archival workflows and stable URLs.
