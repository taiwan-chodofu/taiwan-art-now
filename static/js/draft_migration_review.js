/* Draft read-only migration and conflict-review model; no storage/network writes.
 * A legacy absence NEVER means deletion. Server tombstones are authoritative
 * until a human explicitly resolves them through a separate authenticated flow.
 */
(function(root, factory) {
  const api = factory(
    typeof module === "object" && module.exports
      ? require("./draft_legacy_snapshot.js") : root.TanDraftLegacySnapshot,
    typeof module === "object" && module.exports
      ? require("./draft_versioned_sync.js") : root.TanDraftSync
  );
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftMigrationReview = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function(legacy, sync) {
  "use strict";
  const KINDS = ["favs", "visited"];
  const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
  function preview(storage, serverState) {
    const parsed = legacy.read(storage);
    if (parsed.status !== "ready") return { status: parsed.status, kind: parsed.kind };
    // The sync planner validates the server shape and makes no writes.
    let plan;
    try { plan = sync.plan(parsed.snapshot, serverState); }
    catch (_) { return { status: "invalid_server" }; }
    const rows = [];
    for (const kind of KINDS) {
      const local = parsed.snapshot[kind];
      const remote = serverState[kind];
      const keys = new Set([...Object.keys(local), ...Object.keys(remote)]);
      for (const key of keys) {
        const localPresent = own(local, key);
        const record = remote[key];
        const remotePresent = !!record && !record.deleted;
        let status;
        if (record && record.deleted && localPresent) status = "deleted_remotely";
        else if (record && record.deleted) status = "remote_tombstone";
        else if (localPresent && !record) status = "local_only";
        else if (!localPresent && remotePresent) status = "remote_only";
        else if (localPresent && remotePresent &&
          JSON.stringify(local[key]) === JSON.stringify(record.value)) status = "same";
        else status = "different";
        rows.push(Object.freeze({
          kind, key, status, localPresent, remotePresent,
          // No values in review summary: caller must explicitly request
          // details from already-authorized local/server snapshots.
          remoteRevision: record ? record.revision : null
        }));
      }
    }
    return { status: "ready", revision: serverState.revision,
      safeToWrite: plan.safeToWrite,
      counts: rows.reduce((acc, row) => {
        acc[row.status] = (acc[row.status] || 0) + 1;
        return acc;
      }, Object.create(null)),
      rows };
  }
  return { preview };
});
