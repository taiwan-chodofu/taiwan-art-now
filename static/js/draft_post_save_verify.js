/* DRAFT ONLY: read-only verification of a confirmed server save after local drift.
 * Never repairs localStorage, retries POST, or treats absence as user deletion.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
  ?require("./draft_authenticated_state.js"):root.TanDraftAuthenticatedState);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftPostSaveVerify=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(reader){
 "use strict";
 const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
 async function verify({fetchImpl,committedRevision,changes}={}){
  if(typeof fetchImpl!=="function"||!Number.isSafeInteger(committedRevision)||
     committedRevision<0||!changes||typeof changes!=="object"||
     !changes.favs||!changes.visited)return {status:"invalid_request"};
  const expected=[];
  for(const kind of ["favs","visited"]){
   if(!changes[kind]||Array.isArray(changes[kind])||
      typeof changes[kind]!=="object")return {status:"invalid_request"};
   for(const [key,change] of Object.entries(changes[kind])){
    if(!key||!change||!own(change,"set")||own(change,"delete"))
     return {status:"invalid_request"};
    expected.push({kind,key,value:change.set});
   }
  }
  if(!expected.length)return {status:"invalid_request"};
  const latest=await reader.read({fetchImpl});
  if(latest.status!=="ready")return {status:"could_not_verify",reason:latest.status};
  if(latest.state.revision<committedRevision)
   return {status:"could_not_verify",reason:"older_revision"};
  const unresolved=[];
  for(const {kind,key,value} of expected){
   const entry=latest.state[kind][key];
   if(!entry||entry.deleted||!own(entry,"value")||
      !reader.sameJson(entry.value,value))
    unresolved.push({kind,key,reason:!entry?"not_found":entry.deleted?
      "deleted_on_server":"different_server_value"});
  }
  return unresolved.length
   ?{status:"server_records_need_review",revision:latest.state.revision,unresolved}
   :{status:"confirmed_on_server",revision:latest.state.revision,verifiedCount:expected.length};
 }
 return {verify};
});
