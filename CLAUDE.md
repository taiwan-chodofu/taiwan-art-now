# Claude Code — Taiwan Art Now

## Mandatory session startup (before edits, plans, or commands that mutate files)
1. Read `AGENTS.md`, `DATA_QUALITY_RULES.md`, `docs/ai-handoff/CURRENT.md`, and `docs/ai-handoff/DECISIONS.md`.
2. Run `git status --short --branch` and `git remote -v`; identify local uncommitted work. Do not overwrite it.
3. Run `git fetch origin` (if network access is available), check the latest default branch, and inspect open GitHub PRs/Issues relevant to the task. If network access is unavailable, explicitly report that the remote state is unverified.
4. Identify the active issue/PR and whether ChatGPT or another agent has in-progress work. Do not silently duplicate or conflict with it.
5. Before implementing, briefly report: current branch, last handoff, relevant open PRs, proposed task and tests, risks/blockers. Ask for clarification when task ownership or permissions are unclear.

## Mandatory session close
1. Summarize files changed, decisions, tests actually run (including failures), and any migration/rollback concerns.
2. Update `docs/ai-handoff/CURRENT.md` on your work branch and `DECISIONS.md` when an enduring decision is made.
3. Commit and push the handoff with the feature branch, and link the issue/PR. If unable to push, explicitly provide the uncommitted handoff and reason.
4. Never merge, deploy, rotate credentials, or modify production data without explicit owner approval.

Follow `AGENTS.md` for shared rules. Private ChatGPT conversations are not automatically accessible; GitHub is the shared record.
