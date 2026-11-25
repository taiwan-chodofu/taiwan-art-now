/* DRAFT ONLY. Shared per-item legacy write coordinator; NOT mounted.
 * All tabs and pages must opt into the same Web Lock. Legacy tabs bypass it.
 * No remote synchronization or tombstone inference is performed here.
 */
(function(root, factory) {
  const api = factory(typeof module === "object" && module.exports
    ? require("./draft_legacy_snapshot.js") : root.TanDraftLegacySnapshot);
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftLegacyWriter = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function(legacy) {
  "use strict";
  const LOCK_NAME = "tan-subscriber-legacy-storage-v1";
  const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
  async function mutate({ storage, locks, kind, key, action, value, expectedValue }) {
    if (!storage || typeof storage.getItem !== "function" ||
        typeof storage.setItem !== "function" ||
        !locks || typeof locks.request !== "function" ||
        !["favs", "visited"].includes(kind) ||
        typeof key !== "string" || !key || ["__proto__", "constructor", "prototype"].includes(key) ||
        !["set", "set_if_absent", "remove", "toggle", "remove_if_equal"].includes(action))
      return { status: "not_authorized" };
    try {
      return await locks.request(LOCK_NAME, { mode: "exclusive" }, async () => {
        const current = legacy.read(storage);
        if (current.status !== "ready") return { status: current.status };
        const next = { ...current.snapshot[kind] };
        if(action==="set_if_absent"&&own(next,key))return {status:"unchanged"};
        const resolved = action === "toggle" ? (own(next,key) ? "remove" : "set") : action==="set_if_absent"?"set":action;
        if (resolved === "remove_if_equal") {
          if (!own(next,key)) return {status:"stale_undo"};
          if (JSON.stringify(next[key]) !== JSON.stringify(expectedValue))
            return {status:"stale_undo"};
        }
        if (resolved === "set") {
          const validated = legacy.validateMap({ [key]: value }, kind);
          next[key] = validated[key];
        } else {
          if (!own(next, key)) return { status: "unchanged" };
          delete next[key];
        }
        const storageKey = legacy.KEYS[kind];
        const raw = storage.getItem(storageKey);
        // Re-read raw inside the lock, not a whole-map snapshot from the UI.
        const previous = raw === null ? {} : JSON.parse(raw);
        const verified = legacy.validateMap(previous, kind);
        if (JSON.stringify(verified) !== JSON.stringify(current.snapshot[kind]))
          return { status: "stale_local" };
        // Detect an uncoordinated legacy-tab write immediately before saving.
        // This narrows but cannot eliminate the race with old tabs.
        if (storage.getItem(storageKey) !== raw)
          return { status: "stale_local" };
        storage.setItem(storageKey, JSON.stringify(next));
        // setItem may be silently ignored by a broken storage adapter.
        // Verify the complete map, not merely the selected key.
        const persisted = storage.getItem(storageKey);
        if (persisted !== JSON.stringify(next))
          return { status: "uncertain_write" };
        return { status: "written_under_cooperative_lock", action: resolved === "remove_if_equal" ? "remove" : resolved };
      });
    } catch (_) {
      return { status: "unavailable" };
    }
  }
  return { mutate, LOCK_NAME };
});
