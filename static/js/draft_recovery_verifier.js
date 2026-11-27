/* DRAFT ONLY: revalidate a recovery selection against fresh local/server state.
 * Does not restore, mutate, authenticate or send network requests.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
   ? require("./draft_server_recovery.js"):root.TanDraftServerRecovery);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftRecoveryVerifier=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(recovery){
 "use strict";
 function verify({storage,serverState,expectedRevision,reviewedCandidates,decisions}){
   if(!Number.isSafeInteger(expectedRevision)||expectedRevision<0||
      !Array.isArray(reviewedCandidates)||!Array.isArray(decisions))
     return {status:"invalid_request"};
   if(!serverState||serverState.revision!==expectedRevision)
     return {status:"stale_server"};
   const fresh=recovery.plan({storage,serverState});
   if(!["prepared","needs_review"].includes(fresh.status))
     return {status:fresh.status};
   const byId=new Map(fresh.candidates.map(x=>[JSON.stringify([x.kind,x.key]),x]));
   const reviewed=new Map();
   for(const item of reviewedCandidates){
     if(!item||!["favs","visited"].includes(item.kind)||typeof item.key!=="string"||
        !Number.isSafeInteger(item.item_revision)||item.item_revision<1)
       return {status:"invalid_request"};
     const id=JSON.stringify([item.kind,item.key]);
     if(reviewed.has(id))return {status:"invalid_request"};
     reviewed.set(id,item);
   }
   const accepted=[],seen=new Set();
   for(const d of decisions){
     if(!d||!["favs","visited"].includes(d.kind)||typeof d.key!=="string"||
        !["restore","decide_later"].includes(d.choice))
       return {status:"invalid_request"};
     const id=JSON.stringify([d.kind,d.key]);
     if(seen.has(id)||!reviewed.has(id))return {status:"invalid_request"};
     seen.add(id);
     if(d.choice!=="restore")continue;
     const candidate=byId.get(id),old=reviewed.get(id);
     if(!candidate||candidate.item_revision!==old.item_revision||
        JSON.stringify(candidate.value)!==JSON.stringify(old.value))
       return {status:"stale_review"};
     accepted.push({kind:d.kind,key:d.key,value:candidate.value,
       item_revision:candidate.item_revision});
   }
   return {status:accepted.length?"ready_for_explicit_restore":"nothing_selected",
     accepted,base_revision:expectedRevision,requiresFreshLocalLock:true,
     requiresExplicitWriteConfirmation:true};
 }
 return {verify};
});
