/* DRAFT ONLY: strict same-origin authenticated state reader.
 * Does not infer identity, write, cache, retry, or register a route.
 * Server session ownership is enforced by the unregistered Flask endpoint.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
   ? require("./draft_versioned_sync.js"):root.TanDraftSync);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftAuthenticatedState=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(sync){
 "use strict";
 return {read:sync.read,PATH:sync.PATH,sameJson:sync.sameJson};
});
