/* Draft browser-side v2 sync coordinator. NOT loaded by production templates.
 * No sender/ref identifiers, no silent merge, no automatic conflict retry.
 * Caller owns localStorage and must keep its data intact on failures.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftSync = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const KINDS = ["favs", "visited"];
  const MAX_KEYS = 10000;
  function own(obj, key) { return Object.prototype.hasOwnProperty.call(obj, key); }
  function plain(value) {
    return value !== null && typeof value === "object" &&
      !Array.isArray(value) && (Object.getPrototypeOf(value) === Object.prototype ||
      Object.getPrototypeOf(value) === null);
  }
  // JSON object member order can change across Flask and PostgreSQL JSONB.
  function sameJson(a, b) {
    if (a === b) return true;
    if (Array.isArray(a) || Array.isArray(b))
      return Array.isArray(a) && Array.isArray(b) && a.length === b.length &&
        a.every((value, index) => sameJson(value, b[index]));
    if (!plain(a) || !plain(b)) return false;
    const keys = Object.keys(a);
    return keys.length === Object.keys(b).length &&
      keys.every(key => own(b, key) && sameJson(a[key], b[key]));
  }
  function validateSnapshot(snapshot) {
    if (!plain(snapshot) || Object.keys(snapshot).sort().join(",") !== "favs,visited")
      throw new Error("Invalid snapshot");
    for (const kind of KINDS) {
      if (!plain(snapshot[kind]) || Object.keys(snapshot[kind]).length > MAX_KEYS)
        throw new Error("Invalid collection");
      for (const key of Object.keys(snapshot[kind])) {
        if (!key || key.length > 512 || key === "__proto__" ||
            key === "constructor" || key === "prototype") throw new Error("Invalid key");
      }
    }
    return snapshot;
  }
  function validateServer(state) {
    if (!plain(state) || !Number.isSafeInteger(state.revision) ||
        state.revision < 0 || !plain(state.favs) || !plain(state.visited))
      throw new Error("Invalid server state");
    for (const kind of KINDS) {
      if (Object.keys(state[kind]).length > MAX_KEYS) throw new Error("Invalid collection");
      for (const [key, entry] of Object.entries(state[kind])) {
        if (!key || key.length > 512 || !plain(entry) ||
            typeof entry.deleted !== "boolean" ||
            !Number.isSafeInteger(entry.revision) ||
            entry.revision < 1 || entry.revision > state.revision ||
            !own(entry, "value") ||
            (entry.deleted && entry.value !== null)) throw new Error("Invalid entry");
      }
    }
    return state;
  }
  function plan(local, server) {
    validateSnapshot(local);
    validateServer(server);
    const changes = { favs: Object.create(null), visited: Object.create(null) };
    const conflicts = { favs: [], visited: [] };
    const remoteOnly = { favs: [], visited: [] };
    for (const kind of KINDS) {
      for (const [key, entry] of Object.entries(server[kind])) {
        if (!own(local[kind], key)) {
          if (!entry.deleted) remoteOnly[kind].push(key);
        } else if (entry.deleted || !sameJson(local[kind][key], entry.value)) {
          conflicts[kind].push(key);
        }
      }
      for (const [key, value] of Object.entries(local[kind])) {
        if (!own(server[kind], key)) {
          if (value === null || value === undefined) throw new Error("Invalid local value");
          changes[kind][key] = { set: value };
        }
      }
    }
    const safe = KINDS.every(kind => conflicts[kind].length === 0 &&
      remoteOnly[kind].length === 0);
    return { safeToWrite: safe, baseRevision: server.revision,
      changes, conflicts, remoteOnly };
  }
  async function synchronize({ fetchImpl, localSnapshot }) {
    if (typeof fetchImpl !== "function") throw new Error("Fetch dependency required");
    validateSnapshot(localSnapshot);
    let response;
    try {
      response = await fetchImpl("/api/private-subscribers/v2/state", {
        method: "GET", credentials: "same-origin", cache: "no-store"
      });
    } catch (_) { return { status: "offline" }; }
    if (!response || response.status === 403) return { status: "unauthorized" };
    if (!response.ok) return { status: "unavailable" };
    let server;
    try { server = await response.json(); } catch (_) { return { status: "invalid_server" }; }
    let proposed;
    try { proposed = plan(localSnapshot, server); }
    catch (_) { return { status: "invalid_server" }; }
    if (!proposed.safeToWrite) return { status: "needs_review",
      conflicts: proposed.conflicts, remoteOnly: proposed.remoteOnly };
    if (KINDS.every(kind => Object.keys(proposed.changes[kind]).length === 0))
      return { status: "up_to_date", revision: proposed.baseRevision };
    try {
      response = await fetchImpl("/api/private-subscribers/v2/changes", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ base_revision: proposed.baseRevision, changes: proposed.changes })
      });
    } catch (_) { return { status: "unknown_commit" }; }
    if (!response) return { status: "unknown_commit" };
    if (response.status === 409) return { status: "stale_revision" };
    if (response.status === 403) return { status: "unauthorized" };
    if (!response.ok) return { status: "unavailable" };
    let result;
    try { result = await response.json(); validateServer(result); }
    catch (_) { return { status: "unknown_commit" }; }
    return { status: "saved", revision: result.revision };
  }
  return { plan, synchronize, sameJson };
});
