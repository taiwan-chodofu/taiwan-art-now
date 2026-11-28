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


## 2026-11-27 — Editorial issue #88 (ChatGPT)
Branch `feat/editorial-essays-88`. Added full editorial/001.txt, templates/essay.html, static/essay.css, static/essay.js and two isolated routes in app.py. Static manuscript section/reference counts checked; no runtime or browser tests executed. Next: test routes, exact text and links, verify exhibition record and official dates, integrate navigation, OG/sitemap/GA4 and existing saved-list flow safely. No deployment or merge. Existing security work remains independent.

Follow-up: added home More menu entry, existing mylist deep link, exhibition title search fallback, sitemap and OG locale/site metadata, GA4 editorial events respecting existing exclusion. No direct exhibition ID assumed. Browser/runtime tests, OG image and official source verification remain pending. Draft PR #89.

Follow-up: added 1200x630 PNG OG route using confirmed bundled TC fonts; linked metadata; confirmed existing fotoaura record and dates in manual_exhibitions.json (official Facebook not independently checked). Related route resolves unique source URL dynamically, falls back to search. Added tests/test_editorial.py (not executed). Next run python -m unittest discover -s tests -p test_editorial.py, browser checks, source verification. No merge/deploy.

CI update: runs 46009799654 and 46009788447 passed all four Flask tests and JS syntax check. Added Playwright iPhone 13 WebKit and desktop Chromium checks with screenshots; runs 46009939727 and 46010010806 pending at time of handoff. Publication date label 2026.11.28 is provisional. Before merge, review latest CI and screenshots, verify sources and obtain explicit publication approval. No deployment.

Mobile refinement: stacked footer brand/URL, strict CJK line breaks, 18px body, adaptive margins, 48px share targets, two-column mobile share layout. CI runs 46011873918 and 46011863629 passed existing iPhone/desktop browser tests. Expanded checks to 320/375/430px plus iPhone and desktop, footer geometry, font size and touch target; new results pending. No manuscript edits or deployment.

Editorial navigation added to index, artist and exhibition detail, Discover, search, artists and archive. Search uses exact keyword matches; Discover link is in language menu and needs UX review. CI 46014486601 passed expanded mobile tests after navigation changes. Added template compilation and multilingual card tests in 0175e85; runs 46015252881/46015241953 pending. Existing feature interaction regression and visual/source review remain incomplete. No merge/deploy authorized.

## 2026-11-28 — Editorial second edition (#90)
Owner: ChatGPT; branch `feat/editorial-second-edition-90`. Full approved Traditional Chinese manuscript saved in editorial/001-second.txt (blob 7e67a1fcf541dcb7f5c7adbe71777ca6736e0688); read-back matched submitted text, eight chapters, 30 references and 28 URLs. First manuscript blob matches main. Implemented second route, edition navigation, index, chapter TOC, references, canonical, sitemap and distinct OG image; added Flask regression tests and mobile chapter styling. Tests not yet executed in this session. Next: inspect draft PR CI, extend browser checks for second edition, check actual display and references before explicit publication approval. No production data edits, merge or deploy.
