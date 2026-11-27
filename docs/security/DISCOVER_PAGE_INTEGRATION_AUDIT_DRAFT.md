# Discover integration audit — draft branch only

Scope: `templates/discover.html` on `feat/private-subscriber-storage-adapter-83`. **No production deployment, merge, or approval is implied.**

## Implemented and tested in the draft

- Like/visited persistence is guarded by cooperative Web Locks before advancing the deck. Quota failure retains the card and permits retry.
- Skip does not write a favorite or visited entry; guarded undo restores it.
- Stale undo uses `remove_if_equal` to avoid deleting a newer local entry. It preserves the current deck position and shows an actionable localized message.
- A read-only conflict inspector displays **this device's** saved status, not a server-authoritative or cross-device status. Missing and malformed local data are covered by Chromium tests.
- Undo during animation cancels the delayed render. Rapid repeated actions and simultaneous saves of distinct items across two tabs have Chromium coverage.
- Restart resets the draft undo history without deleting persisted registrations.
- Save-error messages have accessible live-region attributes and mobile-width display checks.
- Actual-template Chromium tests run in `.github/workflows/private-subscriber-tests.yml`, alongside browser-sync, synthetic unit, and disposable PostgreSQL CAS jobs.

Last verified full-green CI: commit `46464f7f88580900c42c2e886de9734196005884`, run `45100394763` (four jobs passed). This is a test result, not a release approval.

## Open blockers / unproven properties

1. **Legacy tabs remain unsafe.** A cached older tab that does not cooperate with Web Locks can overwrite newer localStorage snapshots. Cooperative-lock tests do not cover this.
2. **Cross-device reconciliation is not solved by the Discover integration.** The local inspector cannot claim server state, and this draft does not prove merge semantics or durable deletion tombstones.
3. **Explicit deletion vs registration conflict needs separate resolution semantics.** Preserve both devices' registrations by default; ask only when an explicit deletion history conflicts with a registration. Do not silently select a device or delete data.
4. **Manual mobile and accessibility review is outstanding.** Automated assertions do not establish real-device usability, screen-reader announcements, gesture ergonomics, or animation quality.
5. **End-to-end navigation/back and legacy-tab coexistence need further characterization** before production consideration.

## Release gate

Keep PR #87 in draft. Do not merge or deploy until legacy-writer risks and server reconciliation semantics are addressed, relevant browser tests pass, and manual UX/accessibility review is completed.
