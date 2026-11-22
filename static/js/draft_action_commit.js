/* DRAFT ONLY: UI-facing commit adapter; no production mounting.
 * A successful local write is the sole trigger for UI refresh, notifications,
 * and analytics. Failed/uncertain writes never claim success.
 */
(function(root, factory) {
  const api = factory(typeof module === "object" && module.exports
    ? require("./draft_legacy_writer.js") : root.TanDraftLegacyWriter);
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftActionCommit = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function(writer) {
  "use strict";
  function create({ storage, locks, onCommitted, onFailure, onBusy }) {
    if (!writer || typeof writer.mutate !== "function" ||
        typeof onCommitted !== "function" || typeof onFailure !== "function")
      throw new Error("Explicit writer and callbacks required");
    const pending = new Set();
    async function commit({ kind, key, action, value }) {
      const slot = kind + ":" + key;
      if (pending.has(slot)) return { status: "busy" };
      pending.add(slot);
      if (typeof onBusy === "function") onBusy(true, { kind, key });
      try {
        const result = await writer.mutate({ storage, locks, kind, key, action, value });
        if (result.status === "written_under_cooperative_lock") {
          // Re-read after persistence; no stale optimistic UI.
          const raw = storage.getItem(kind === "favs" ? "taiwan_art_favs" : "taiwan_art_visited");
          const parsed = JSON.parse(raw);
          const present = Object.prototype.hasOwnProperty.call(parsed, key);
          if ((action === "set" && !present) || (action === "remove" && present)) {
            onFailure({ status: "uncertain_write" }, { kind, key, action });
            return { status: "uncertain_write" };
          }
          onCommitted({ kind, key, action, value: present ? parsed[key] : undefined });
        } else if (result.status !== "unchanged") {
          onFailure(result, { kind, key, action });
        }
        return result;
      } catch (_) {
        const result = { status: "unavailable" };
        onFailure(result, { kind, key, action });
        return result;
      } finally {
        pending.delete(slot);
        if (typeof onBusy === "function") onBusy(false, { kind, key });
      }
    }
    return { commit };
  }
  return { create };
});
