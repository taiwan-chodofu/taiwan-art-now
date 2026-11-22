/* Additive-first draft reconciliation. No storage writes or network requests.
 * Legacy absence is not deletion. A server tombstone + local registration
 * requires review; remote-only active registrations are retained.
 */
(function(root, factory) {
  const api = factory(
    typeof module === "object" && module.exports
      ? require("./draft_legacy_snapshot.js") : root.TanDraftLegacySnapshot,
    typeof module === "object" && module.exports
      ? require("./draft_versioned_sync.js") : root.TanDraftSync
  );
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftAdditiveMerge = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function(legacy, sync) {
  "use strict";
  const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
  const kinds = ["favs", "visited"];
  function plan(storage, serverState) {
    const parsed = legacy.read(storage);
    if (parsed.status !== "ready") return { status: parsed.status, kind: parsed.kind };
    // Strictly validate server state using existing coordinator.
    try { sync.plan(parsed.snapshot, serverState); }
    catch (_) { return { status: "invalid_server" }; }
    const changes = { favs: Object.create(null), visited: Object.create(null) };
    const review = [];
    const preservedRemote = [];
    const same = [];
    const metadataDifferences = [];
    for (const kind of kinds) {
      for (const [key, value] of Object.entries(parsed.snapshot[kind])) {
        if (!own(serverState[kind], key)) {
          changes[kind][key] = { set: value };
          continue;
        }
        const remote = serverState[kind][key];
        if (remote.deleted) {
          review.push({ kind, key, reason: "explicit_deletion_conflict" });
        } else if (JSON.stringify(value) === JSON.stringify(remote.value)) {
          same.push({ kind, key });
        } else {
          // Same exhibition remains saved; differing metadata/timestamps
          // must not be silently overwritten. Preserve server value.
          metadataDifferences.push({ kind, key, reason: "metadata_diff_preserved" });
        }
      }
      for (const [key, remote] of Object.entries(serverState[kind])) {
        if (!own(parsed.snapshot[kind], key) && !remote.deleted)
          preservedRemote.push({ kind, key });
      }
    }
    return { status: review.length ? "needs_review" : "prepared",
      base_revision: serverState.revision, changes, review, preservedRemote,
      same, metadataDifferences };
  }
  return { plan };
});
