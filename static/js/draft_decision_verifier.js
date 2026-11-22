/* Draft decision verifier; NEVER sends writes or changes localStorage.
 * Caller must obtain fresh state and rebuild preview before any future commit.
 */
(function(root, factory) {
  const api = factory(
    typeof module === "object" && module.exports
      ? require("./draft_migration_review.js") : root.TanDraftMigrationReview,
    typeof module === "object" && module.exports
      ? require("./draft_legacy_snapshot.js") : root.TanDraftLegacySnapshot
  );
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftDecisionVerifier = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function(migration, legacy) {
  "use strict";
  const KINDS = ["favs", "visited"];
  const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
  function verify({ storage, serverState, expectedRevision, decisions }) {
    if (!Number.isSafeInteger(expectedRevision) || expectedRevision < 0 ||
        !serverState || serverState.revision !== expectedRevision)
      return { status: "stale_revision" };
    const report = migration.preview(storage, serverState);
    if (report.status !== "ready") return { status: report.status };
    if (!Array.isArray(decisions)) return { status: "invalid_decisions" };
    const pending = new Map(report.rows.filter(row =>
      ["remote_only", "different", "deleted_remotely"].includes(row.status))
      .map(row => [JSON.stringify([row.kind, row.key]), row]));
    const selected = new Map();
    for (const decision of decisions) {
      if (!decision || typeof decision !== "object" ||
          Object.keys(decision).sort().join(",") !== "choice,key,kind" ||
          !KINDS.includes(decision.kind) || typeof decision.key !== "string" ||
          !["keep_local", "keep_remote", "decide_later"].includes(decision.choice))
        return { status: "invalid_decisions" };
      const id = JSON.stringify([decision.kind, decision.key]);
      if (!pending.has(id) || selected.has(id))
        return { status: "invalid_decisions" };
      selected.set(id, decision.choice);
    }
    // Unanswered items are intentionally treated as decide_later.
    const unresolved = [];
    const proposals = [];
    const parsed = legacy.read(storage);
    if (parsed.status !== "ready") return { status: parsed.status };
    for (const [id, row] of pending) {
      const choice = selected.get(id) || "decide_later";
      if (choice === "decide_later") {
        unresolved.push({ kind: row.kind, key: row.key, reason: row.status });
        continue;
      }
      if (choice === "keep_remote") {
        // Local replacement/removal is intentionally NOT implemented:
        // another tab may have changed localStorage since the preview.
        unresolved.push({ kind: row.kind, key: row.key, reason: "local_apply_not_implemented" });
        continue;
      }
      if (row.status === "remote_only") {
        // Local absence is not an affirmative deletion instruction.
        unresolved.push({ kind: row.kind, key: row.key, reason: "local_absence_not_deletion" });
        continue;
      }
      if (row.status === "deleted_remotely") {
        // Never resurrect a tombstone from stale local data.
        unresolved.push({ kind: row.kind, key: row.key, reason: "tombstone_requires_separate_confirmation" });
        continue;
      }
      if (!own(parsed.snapshot[row.kind], row.key)) return { status: "invalid_local" };
      // Proposals are previews only; no request is ever constructed or sent.
      proposals.push({ kind: row.kind, key: row.key,
        action: "set", expectedItemRevision: row.remoteRevision });
    }
    // Local-only records are safe additions only if a future authenticated
    // writer revalidates the exact server revision and full local snapshot.
    for (const row of report.rows.filter(row => row.status === "local_only"))
      proposals.push({ kind: row.kind, key: row.key, action: "set",
        expectedItemRevision: null });
    return { status: unresolved.length ? "requires_review" : "prepared",
      baseRevision: expectedRevision, proposals, unresolved };
  }
  return { verify };
});
