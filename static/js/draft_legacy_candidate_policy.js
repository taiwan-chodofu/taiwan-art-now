/* DRAFT ONLY: read-only classification; no local or remote writes.
 * Delegate validation to the same strict adapters as the migration planner.
 */
(function(root,factory){
 const api=factory(
  typeof module==="object"&&module.exports?require("./draft_legacy_snapshot.js"):root.TanDraftLegacySnapshot,
  typeof module==="object"&&module.exports?require("./draft_versioned_sync.js"):root.TanDraftSync);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftLegacyCandidatePolicy=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(legacyAdapter,sync){
 "use strict";
 const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
 function classify({legacy,server}={}){
  try{
   if(!legacy||!server||Object.keys(legacy).sort().join(",")!=="favs,visited")
    throw new Error("Invalid legacy snapshot");
   const snapshot={
    favs:legacyAdapter.validateMap(legacy.favs,"favs"),
    visited:legacyAdapter.validateMap(legacy.visited,"visited")
   };
   // plan validates server revision, entry schema, key sizes, and provenance.
   sync.plan(snapshot,server);
   const adds=[],reviews=[];
   for(const kind of ["favs","visited"]){
    for(const [key,value] of Object.entries(snapshot[kind])){
     if(!own(server[kind],key))adds.push({kind,key,value});
     else if(server[kind][key].deleted)
      reviews.push({kind,key,reason:"server_tombstone"});
    }
   }
   return {status:"classified",adds,reviews,base_revision:server.revision,
    requiresServerCAS:true};
  }catch(_){return {status:"invalid_input",adds:[],reviews:[]};}
 }
 return {classify};
});
