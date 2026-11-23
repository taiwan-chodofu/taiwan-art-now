/* DRAFT ONLY: cooperative Web Locks guard for legacy localStorage mutations.
 * Every writer in every tab must use the SAME exclusive lock name; legacy
 * writers that bypass this protocol can still race. Not production mounted.
 */
(function(root, factory) {
  const api = factory(typeof module === "object" && module.exports
    ? require("./draft_legacy_snapshot.js") : root.TanDraftLegacySnapshot);
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftCoordinatedLocalRemoval = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function(legacy) {
  "use strict";
  const LOCK_NAME = "tan-subscriber-legacy-storage-v1";
  const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
  async function remove({ storage, locks, decision, reviewedSnapshot,
                          serverState, expectedServerRevision, fetchFreshState }) {
    if (!locks || typeof locks.request !== "function" ||
        typeof fetchFreshState !== "function" || !storage ||
        typeof storage.getItem !== "function" || typeof storage.setItem !== "function" ||
        !decision || decision.choice !== "remove_from_list" ||
        !["favs", "visited"].includes(decision.kind) ||
        typeof decision.key !== "string" || !decision.key ||
        !reviewedSnapshot || !serverState ||
        !Number.isSafeInteger(expectedServerRevision) ||
        serverState.revision !== expectedServerRevision)
      return { status: "not_authorized" };
    try {
      return await locks.request(LOCK_NAME, { mode: "exclusive" }, async () => {
        const fresh = await fetchFreshState();
        const kind = decision.kind, key = decision.key;
        const entry = fresh && fresh[kind] && fresh[kind][key];
        const original = serverState[kind] && serverState[kind][key];
        if (!fresh || fresh.revision !== expectedServerRevision ||
            !Number.isSafeInteger(fresh.revision) || fresh.revision < 1 ||
            !original || !original.deleted ||
            !Number.isSafeInteger(original.revision) || original.revision < 1 ||
            !entry || !entry.deleted ||
            !Number.isSafeInteger(entry.revision) ||
            entry.revision !== original.revision)
          return { status: "stale_server" };
        const current = legacy.read(storage);
        if (current.status !== "ready" ||
            JSON.stringify(current.snapshot) !== JSON.stringify(reviewedSnapshot))
          return { status: "stale_local" };
        if (!reviewedSnapshot[kind] || !own(reviewedSnapshot[kind], key))
          return { status: "not_authorized" };
        const storageKey = legacy.KEYS[kind];
        const raw = storage.getItem(storageKey);
        if (raw === null) return { status: "stale_local" };
        const parsed = JSON.parse(raw);
        const validated = legacy.validateMap(parsed, kind);
        if (!own(validated, key) ||
            JSON.stringify(validated[key]) !==
              JSON.stringify(reviewedSnapshot[kind][key]))
          return { status: "stale_local" };
        delete parsed[key];
        if (storage.getItem(storageKey) !== raw) return { status: "stale_local" };
        storage.setItem(storageKey, JSON.stringify(parsed));
        const after = legacy.read(storage);
        const expected = { ...reviewedSnapshot[kind] };
        delete expected[key];
        if (after.status !== "ready" ||
            JSON.stringify(after.snapshot[kind]) !== JSON.stringify(expected) ||
            JSON.stringify(after.snapshot[kind === "favs" ? "visited" : "favs"]) !==
              JSON.stringify(reviewedSnapshot[kind === "favs" ? "visited" : "favs"]))
          return { status: "uncertain_write" };
        return { status: "removed_under_cooperative_lock" };
      });
    } catch (_) {
      return { status: "unavailable" };
    }
  }
  return { remove, LOCK_NAME };
});
