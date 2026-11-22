/* Exhibition-first decision verifier. Isolated preview only: no API/storage writes.
 * A future writer MUST re-fetch current state and use authenticated atomic CAS.
 */
(function(root, factory) {
  const api = factory(
    typeof module === "object" && module.exports
      ? require("./draft_additive_merge.js") : root.TanDraftAdditiveMerge,
    typeof module === "object" && module.exports
      ? require("./draft_legacy_snapshot.js") : root.TanDraftLegacySnapshot
  );
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftDecisionVerifier = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function(merge, legacy) {
  "use strict";
  const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
  function verify({ storage, serverState, expectedRevision, expectedLocalSnapshot, decisions }) {
    if (!Number.isSafeInteger(expectedRevision) || expectedRevision < 0 ||
        !serverState || serverState.revision !== expectedRevision)
      return { status: "stale_revision" };
    const parsed = legacy.read(storage);
    if (parsed.status !== "ready") return { status: parsed.status };
    // Caller must retain the exact reviewed local snapshot; do not trust a
    // decision if another tab changed localStorage after the UI was displayed.
    if (!expectedLocalSnapshot ||
        JSON.stringify(parsed.snapshot) !== JSON.stringify(expectedLocalSnapshot))
      return { status: "stale_local_snapshot" };
    const report = merge.plan(storage, serverState);
    if (!["prepared", "needs_review"].includes(report.status))
      return { status: report.status };
    if (!Array.isArray(decisions)) return { status: "invalid_decisions" };
    const conflicts = new Map(report.review.map(item =>
      [JSON.stringify([item.kind, item.key]), item]));
    const selected = new Map();
    for (const d of decisions) {
      if (!d || typeof d !== "object" ||
          Object.keys(d).sort().join(",") !== "choice,key,kind" ||
          !["favs", "visited"].includes(d.kind) || typeof d.key !== "string" ||
          !["keep_saved", "remove_from_list", "decide_later"].includes(d.choice))
        return { status: "invalid_decisions" };
      const id = JSON.stringify([d.kind, d.key]);
      if (!conflicts.has(id) || selected.has(id))
        return { status: "invalid_decisions" };
      selected.set(id, d.choice);
    }
    const unresolved = [];
    const proposals = [];
    for (const item of report.review) {
      const choice = selected.get(JSON.stringify([item.kind, item.key])) || "decide_later";
      if (choice === "decide_later") {
        unresolved.push({ kind: item.kind, key: item.key, reason: "user_deferred" });
        continue;
      }
      if (!own(parsed.snapshot[item.kind], item.key) ||
          !own(serverState[item.kind], item.key) ||
          !serverState[item.kind][item.key].deleted)
        return { status: "stale_conflict" };
      if (choice === "keep_saved") {
        // Only explicit affirmative choice can propose tombstone resurrection.
        proposals.push({ kind: item.kind, key: item.key, action: "set",
          expectedItemRevision: serverState[item.kind][item.key].revision,
          requiresAuthenticatedCAS: true });
      } else {
        // Existing server tombstone already represents removal. Local removal
        // requires its own safe compare-and-swap implementation, not this draft.
        unresolved.push({ kind: item.kind, key: item.key,
          reason: "local_removal_not_implemented" });
      }
    }
    for (const kind of ["favs", "visited"]) {
      for (const key of Object.keys(report.changes[kind]))
        proposals.push({ kind, key, action: "set", expectedItemRevision: null,
          requiresAuthenticatedCAS: true });
    }
    return { status: unresolved.length ? "requires_review" : "prepared",
      baseRevision: expectedRevision, proposals, unresolved };
  }
  return { verify };
});
