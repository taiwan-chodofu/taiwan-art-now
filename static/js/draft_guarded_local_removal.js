/* Draft-only guarded local removal for an explicitly reviewed server tombstone.
 * localStorage has NO atomic compare-and-swap across tabs. This adapter
 * checks immediately before setItem and verifies afterwards, but cannot
 * guarantee safety against another tab writing in the intervening instant.
 * NOT mounted in production; do not treat as a cross-tab atomic operation.
 */
(function(root, factory) {
  const api = factory(typeof module === "object" && module.exports
    ? require("./draft_legacy_snapshot.js") : root.TanDraftLegacySnapshot);
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftGuardedLocalRemoval = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function(legacy) {
  "use strict";
  const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
  function remove({ storage, decision, reviewedSnapshot, serverState, expectedServerRevision }) {
    if (!storage || typeof storage.getItem !== "function" ||
        typeof storage.setItem !== "function" ||
        !decision || decision.choice !== "remove_from_list" ||
        !["favs", "visited"].includes(decision.kind) ||
        typeof decision.key !== "string" || !decision.key ||
        !reviewedSnapshot || !serverState ||
        !Number.isSafeInteger(expectedServerRevision) ||
        expectedServerRevision !== serverState.revision)
      return { status: "not_authorized" };
    const kind = decision.kind, key = decision.key;
    const entry = serverState[kind] && serverState[kind][key];
    if (!entry || !entry.deleted || !Number.isSafeInteger(entry.revision) ||
        entry.revision > expectedServerRevision ||
        !reviewedSnapshot[kind] || !own(reviewedSnapshot[kind], key))
      return { status: "not_authorized" };
    try {
      const before = legacy.read(storage);
      if (before.status !== "ready" ||
          JSON.stringify(before.snapshot) !== JSON.stringify(reviewedSnapshot))
        return { status: "stale_local" };
      const storageKey = legacy.KEYS[kind];
      const raw = storage.getItem(storageKey);
      if (raw === null) return { status: "stale_local" };
      const parsed = JSON.parse(raw);
      const validated = legacy.validateMap(parsed, kind);
      if (!own(validated, key) ||
          JSON.stringify(validated[key]) !== JSON.stringify(reviewedSnapshot[kind][key]))
        return { status: "stale_local" };
      delete parsed[key];
      // Recheck the exact raw bytes just before writing. This is a guard,
      // not atomic CAS; another tab can still race between read and write.
      if (storage.getItem(storageKey) !== raw) return { status: "stale_local" };
      storage.setItem(storageKey, JSON.stringify(parsed));
      const after = legacy.read(storage);
      if (after.status !== "ready" || own(after.snapshot[kind], key))
        return { status: "uncertain_write" };
      return { status: "removed_locally_non_atomic" };
    } catch (_) {
      return { status: "storage_unavailable" };
    }
  }
  return { remove };
});
