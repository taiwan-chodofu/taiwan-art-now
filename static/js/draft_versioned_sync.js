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
 const PATH="/api/private-subscribers/v2/state";
 const trustedWorkers=new WeakSet();
 async function supportsPrivateReads(worker){
   if(!worker||trustedWorkers.has(worker))return true;
   if(typeof MessageChannel!=="function")return false;
   const marker="tan-private-network-only-v1";
   return new Promise(resolve=>{
     const channel=new MessageChannel();
     const finish=ok=>{
       clearTimeout(timer);
       channel.port1.close();
       if(ok)trustedWorkers.add(worker);
       resolve(ok);
     };
     const timer=setTimeout(()=>finish(false),1500);
     channel.port1.onmessage=e=>finish(e.data===marker);
     try{worker.postMessage(marker,[channel.port2]);}
     catch(_){channel.port2.close();finish(false);}
   });
 }
 async function read({fetchImpl,serviceWorker=globalThis.navigator?.serviceWorker}){
   if(typeof fetchImpl!=="function")return {status:"invalid_request"};
   const controller=serviceWorker?.controller;
   if(controller&&(!await supportsPrivateReads(controller)||serviceWorker?.controller!==controller))
     return {status:"worker_update_required"};
   let response;
   try{response=await fetchImpl(PATH,{method:"GET",credentials:"same-origin",
     cache:"no-store",redirect:"error",mode:"same-origin",
     headers:{"Accept":"application/json"}});}
   catch(_){return {status:"unavailable",offline:true};}
   if(!response)return {status:"unavailable"};
   if(response.status===401||response.status===403)return {status:"unauthorized"};
   if(!response.ok)return {status:"unavailable"};
   // A login redirect, HTML response or cacheable response must never be
   // interpreted as an authenticated, current subscriber state.
   const contentType=response.headers&&typeof response.headers.get==="function"
     ? response.headers.get("content-type"):null;
   const cacheControl=response.headers&&typeof response.headers.get==="function"
     ? response.headers.get("cache-control"):null;
   if(!contentType||!/^application\/json(?:\s*;|\s*$)/i.test(contentType)||
      !cacheControl||!/(?:^|,)\s*no-store\b/i.test(cacheControl))
     return {status:"invalid_response"};
   let state;
   try{state=await response.json();validateServer(state);}
   catch(_){return {status:"invalid_server"};}
   if(serviceWorker?.controller!==controller)return {status:"worker_update_required"};
   return {status:"ready",state};
 }
  async function synchronize({ fetchImpl, localSnapshot, serviceWorker }) {
    if (typeof fetchImpl !== "function") throw new Error("Fetch dependency required");
    validateSnapshot(localSnapshot);
    const latest = await read({fetchImpl, serviceWorker});
    if (latest.status !== "ready") return {status: latest.offline ? "offline" : latest.status};
    const server = latest.state;
    let response;
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
    if (!response.ok) return { status: "unknown_commit" };
    let result;
    try { result = await response.json(); validateServer(result); }
    catch (_) { return { status: "unknown_commit" }; }
    const verified = await read({fetchImpl, serviceWorker});
    if (verified.status !== "ready" || result.revision <= proposed.baseRevision ||
        verified.state.revision !== result.revision ||
        !KINDS.every(kind => Object.entries(proposed.changes[kind]).every(([key, op]) => {
          const entry = verified.state[kind][key];
          return entry && !entry.deleted && entry.revision === result.revision &&
            sameJson(entry.value, op.set);
        }))) return { status: "unknown_commit" };
    return { status: "saved", revision: result.revision };
  }
  return { plan, synchronize, sameJson, read, PATH };
});
