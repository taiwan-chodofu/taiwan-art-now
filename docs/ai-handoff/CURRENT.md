# Current AI handoff

Updated: 2026-11-22
Author: ChatGPT
Status: Collaboration infrastructure proposed on `chore/ai-handoff-foundation`; awaiting review and merge.

## Goal
Establish a durable handoff between ChatGPT and Claude Code for Taiwan Art Now, then address the highest-priority security and data-integrity issues incrementally.

## Findings from prior static code review (reconfirm before implementing)
- `app.py`: subscriber and Web Push mutation endpoints rely on caller-supplied identifiers; review authentication/authorization and backwards compatibility.
- `app.py`: preview-token fallback should be removed or fail closed; review deployment configuration.
- `scraper.py`: expired exhibition handling can write manual/archive files during scraping; review side effects and data consistency.
- `.github/workflows/archive-expired.yml`: archive and validation steps use `|| true`; investigate correct no-op versus error exit semantics.
- Exhibition detail and OG URLs use museum-local array indexes, which may change after reordering.

## Proposed implementation order
1. Security: subscriber API authorization and preview access. Design safe migration for existing users before code changes.
2. Data integrity: archive/validation workflow, atomic writes, tests, and failure handling.
3. Stable exhibition IDs: legacy redirects and migration for local favorites/visited references.

## Current work
- Created shared AI collaboration rules, Claude Code entry point, and handoff/decision log in a feature branch.
- No application code or production exhibition/subscriber data changed.
- No runtime tests run for application behavior.

## Next agent
- Review this collaboration PR; do not merge without owner approval.
- After merge, open a scoped issue for security review and implementation.
- Before modifying subscriber flows, document threat model, credential verification, backward-compatible migration, rollback and tests.

## Source of truth
Repository: https://github.com/taiwan-chodofu/taiwan-art-now
This file records shared work only; private AI conversation history is not automatically synced.
