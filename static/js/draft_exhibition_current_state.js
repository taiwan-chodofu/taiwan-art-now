/* DRAFT ONLY: read-only current saved state for one exhibition.
 * Never retries a save, restores a deletion, or writes to local storage.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
  ?require("./draft_authenticated_state.js"):root.TanDraftAuthenticatedState);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftExhibitionCurrentState=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(reader){
 "use strict";
 const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
 async function check({fetchImpl,exhibitionKey}={}){
  if(typeof exhibitionKey!=="string"||!exhibitionKey.trim()||
     typeof fetchImpl!=="function")return {status:"invalid_request"};
  const response=await reader.read({fetchImpl});
  if(response.status!=="ready")
   return {status:"unconfirmed",reason:response.status};
  const state=response.state;
  if(!state||!Number.isSafeInteger(state.revision)||
     !state.favs||!state.visited)return {status:"unconfirmed",reason:"invalid_state"};
  const kinds=["favs","visited"];
  const entries=kinds.map(kind=>({
   kind,entry:own(state[kind],exhibitionKey)?state[kind][exhibitionKey]:null
  }));
  const active=entries.filter(({entry})=>entry&&entry.deleted===false);
  const deleted=entries.filter(({entry})=>entry&&entry.deleted===true);
  if(active.length)return {status:"saved",revision:state.revision,
   collections:active.map(({kind})=>kind),
   removedCollections:deleted.map(({kind})=>kind)};
  if(deleted.length)return {status:"removed",revision:state.revision,
   collections:deleted.map(({kind})=>kind)};
  return {status:"not_found",revision:state.revision};
 }
 return {check};
});
