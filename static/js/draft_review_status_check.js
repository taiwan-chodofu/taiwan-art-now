/* Draft-only, read-only post-confirmation status check. Never retries a write. */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
   ?require("./draft_authenticated_state.js"):root.TanDraftAuthenticatedState);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftReviewStatusCheck=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(reader){
 "use strict";
 const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
 const canonical=x=>JSON.stringify(x,Object.keys(x||{}).sort());
 async function check({fetchImpl,kind,key,expectedValue}={}){
   if(!["favs","visited"].includes(kind)||typeof key!=="string"||!key||
       expectedValue===undefined||expectedValue===null)
     return {status:"invalid_request"};
   const latest=await reader.read({fetchImpl});
   if(latest.status!=="ready")return {status:"unverified",reason:latest.status};
   const entry=latest.state[kind][key];
   if(!entry)return {status:"not_found",revision:latest.state.revision};
   if(entry.deleted)return {status:"still_deleted",revision:latest.state.revision};
   if(!own(entry,"value"))return {status:"unverified",reason:"missing_value"};
   return {status:canonical(entry.value)===canonical(expectedValue)
     ?"saved_on_server":"different_server_value",revision:latest.state.revision};
 }
 return {check,readState:reader.read};
});
