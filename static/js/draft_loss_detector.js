/* DRAFT ONLY: detect stale-tab loss against a previously verified local snapshot.
 * Read-only; never interprets absence as a deletion and never restores data.
 * A checkpoint must come from a trusted completed write or verified import.
 */
(function(root, factory) {
  const api = factory(typeof module === "object" && module.exports
    ? require("./draft_legacy_snapshot.js") : root.TanDraftLegacySnapshot);
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftLossDetector = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function(legacy) {
  "use strict";
  function inspect({ storage, checkpoint }) {
    if (!checkpoint || typeof checkpoint !== "object" ||
        !checkpoint.favs || !checkpoint.visited)
      return { status: "invalid_checkpoint" };
    let trusted;
    try {
      trusted = {
        favs: legacy.validateMap(checkpoint.favs, "favs"),
        visited: legacy.validateMap(checkpoint.visited, "visited")
      };
    } catch (_) { return { status: "invalid_checkpoint" }; }
    const current = legacy.read(storage);
    if (current.status !== "ready")
      return { status: current.status, kind: current.kind };
    const missing = [], changed = [], additions = [];
    for (const kind of ["favs", "visited"]) {
      for (const [key, value] of Object.entries(trusted[kind])) {
        if (!Object.prototype.hasOwnProperty.call(current.snapshot[kind], key))
          missing.push({kind, key, reason:"checkpoint_entry_missing"});
        else if (JSON.stringify(value) !== JSON.stringify(current.snapshot[kind][key]))
          changed.push({kind, key, reason:"checkpoint_metadata_changed"});
      }
      for (const key of Object.keys(current.snapshot[kind])) {
        if (!Object.prototype.hasOwnProperty.call(trusted[kind], key))
          additions.push({kind, key});
      }
    }
    return {status: missing.length || changed.length ? "needs_review" : "consistent",
      missing, changed, additions};
  }
  return {inspect};
});
