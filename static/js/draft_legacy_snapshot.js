/* Read-only adapter for existing Taiwan Art Now localStorage shapes.
 * DRAFT ONLY; does not write, remove or synchronize any browser data.
 * Existing maps: favs[key]={title,museum,dates,url}; visited[key]=ISO timestamp.
 * Legacy deletes remove keys, so absence is NOT a tombstone.
 */
(function(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftLegacySnapshot = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function() {
  "use strict";
  const KEYS = Object.freeze({ favs: "taiwan_art_favs", visited: "taiwan_art_visited" });
  const MAX_ITEMS = 10000;
  const MAX_KEY = 512;
  const MAX_FIELD = 4096;
  const FAV_FIELDS = ["title", "museum", "dates", "url", "region", "event"];
  const VISITED_FIELDS = ["date", "title", "museum", "dates", "url", "region"];
  const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
  const plain = (obj) => obj !== null && typeof obj === "object" &&
    !Array.isArray(obj) && (Object.getPrototypeOf(obj) === Object.prototype ||
      Object.getPrototypeOf(obj) === null);
  function validateMap(value, kind) {
    if (!plain(value) || Object.keys(value).length > MAX_ITEMS)
      throw new Error("Invalid legacy " + kind + " map");
    const result = Object.create(null);
    for (const [key, item] of Object.entries(value)) {
      if (!key || key.length > MAX_KEY || ["__proto__", "constructor", "prototype"].includes(key))
        throw new Error("Invalid exhibition key");
      if (kind === "visited") {
        if (typeof item !== "string" || item.length > 128 ||
            !Number.isFinite(Date.parse(item)) ||
            !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d/.test(item))
          throw new Error("Invalid visited timestamp");
        result[key] = item;
      } else {
        if (!plain(item) || Object.keys(item).some(field => !FAV_FIELDS.includes(field)))
          throw new Error("Invalid favorite item");
        const normalized = Object.create(null);
        for (const field of FAV_FIELDS) {
          if (own(item, field)) {
            if (typeof item[field] !== "string" || item[field].length > MAX_FIELD)
              throw new Error("Invalid favorite field");
            normalized[field] = item[field];
          }
        }
        if (!own(normalized, "title") || !own(normalized, "museum"))
          throw new Error("Incomplete favorite item");
        result[key] = normalized;
      }
    }
    return result;
  }
  function read(storage) {
    if (!storage || typeof storage.getItem !== "function")
      throw new Error("Storage dependency required");
    const snapshot = {};
    for (const kind of ["favs", "visited"]) {
      let raw;
      try { raw = storage.getItem(KEYS[kind]); }
      catch (_) { return { status: "unavailable" }; }
      if (raw === null) { snapshot[kind] = Object.create(null); continue; }
      try { snapshot[kind] = validateMap(JSON.parse(raw), kind); }
      catch (_) { return { status: "invalid_local", kind }; }
    }
    return { status: "ready", snapshot };
  }
  return { read, validateMap, KEYS };
});
