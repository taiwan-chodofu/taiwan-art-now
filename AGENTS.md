# Taiwan Art Now — Shared AI Collaboration Rules

This file is the shared entry point for ChatGPT, Claude Code, and other coding agents.

## Start every session
1. Read `DATA_QUALITY_RULES.md`; verify exhibition details against official sources. Do not invent or machine-translate official Traditional Chinese titles.
2. Read `docs/ai-handoff/CURRENT.md` and `docs/ai-handoff/DECISIONS.md`.
3. Check the current branch, Git status, related GitHub Issue and PR before editing.
4. Read relevant implementation and tests before making changes.

## Collaboration
- GitHub Issues track tasks; pull requests track implementation and review.
- Use a separate branch and PR for each bounded change. Do not push directly to `main`.
- Before handing off, update `docs/ai-handoff/CURRENT.md` on your branch: objective, completed work, files changed, tests actually run, outstanding issues, and exact next steps.
- Record durable architectural/product decisions in `docs/ai-handoff/DECISIONS.md` with date, rationale, status and tradeoffs.
- Distinguish verified findings from hypotheses and pending decisions. Link evidence to code paths, issues or PRs.
- Never assume private ChatGPT or Claude conversations are synchronized; only explicitly committed handoffs are shared.
- Do not overwrite another agent's work; inspect pending branches and PRs first.

## Safety and release
- Never commit credentials, subscriber IDs, private tokens, personal data, or private conversation transcripts.
- Do not deploy, merge, rotate credentials, or mutate production data without explicit approval.
- Preserve existing exhibition records, favorites/visited state, subscriber integrations, and URLs unless a migration is approved.
- Add regression tests for subscriber authorization, archival workflows, and stable URLs.
- Do not claim tests passed unless executed. Clearly label untested work.
