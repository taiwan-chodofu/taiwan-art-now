/* DRAFT ONLY. Append-only local checkpoint, not mounted or server-backed.
 * This is a recovery aid, NOT a durable guarantee: clearing browser storage,
 * eviction, a malicious script or device loss may remove every checkpoint.
 * Never changes legacy keys, never restores, never infers deletion.
 */
(function(root, factory) {
  const api = factory(typeof module === "object" && module.exports
    ? require("./draft_legacy_snapshot.js") : root.TanDraftLegacySnapshot);
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftCheckpoint = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function(legacy) {
  "use strict";
  const PREFIX = "tan_draft_checkpoint_v1_";
  const own = (o,k) => Object.prototype.hasOwnProperty.call(o,k);
  function canonical(snapshot) {
    return JSON.stringify({favs:legacy.validateMap(snapshot.favs,"favs"),
      visited:legacy.validateMap(snapshot.visited,"visited")});
  }
  function save({storage, id, snapshot}) {
    if (!storage || typeof storage.getItem !== "function" ||
        typeof storage.setItem !== "function" ||
        typeof id !== "string" || !/^[a-zA-Z0-9_-]{8,80}$/.test(id))
      return {status:"invalid_request"};
    let encoded;
    try { encoded=canonical(snapshot); }
    catch (_) { return {status:"invalid_snapshot"}; }
    const key=PREFIX+id;
    try {
      // Checkpoints must never replace existing bytes, even when identical.
      if (storage.getItem(key)!==null) return {status:"already_exists"};
      storage.setItem(key,encoded);
      if (storage.getItem(key)!==encoded) return {status:"uncertain_write"};
      return {status:"saved",key};
    } catch (_) { return {status:"unavailable"}; }
  }
  function load({storage,id}) {
    if (!storage || typeof storage.getItem !== "function" ||
        typeof id !== "string" || !/^[a-zA-Z0-9_-]{8,80}$/.test(id))
      return {status:"invalid_request"};
    try {
      const raw=storage.getItem(PREFIX+id);
      if (raw===null) return {status:"missing"};
      const decoded=JSON.parse(raw);
      if (!decoded || typeof decoded!=="object" ||
          !own(decoded,"favs") || !own(decoded,"visited") ||
          Object.keys(decoded).length!==2)
        return {status:"invalid_checkpoint"};
      return {status:"ready",snapshot:JSON.parse(canonical(decoded))};
    } catch (_) { return {status:"invalid_checkpoint"}; }
  }
  function capture({storage,id}) {
    const current=legacy.read(storage);
    if (current.status!=="ready") return current;
    return save({storage,id,snapshot:current.snapshot});
  }
  return {save,load,capture,PREFIX};
});
