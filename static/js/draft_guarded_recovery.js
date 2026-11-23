/* DRAFT ONLY: consent-gated single-item local restore. Never mounted.
 * A caller must supply an authenticated fresh-state fetch. Only cooperative
 * tabs honor Web Locks; old cached tabs can still overwrite this result.
 */
(function(root,factory){
 const api=factory(
  typeof module==="object"&&module.exports?require("./draft_legacy_snapshot.js"):root.TanDraftLegacySnapshot,
  typeof module==="object"&&module.exports?require("./draft_recovery_verifier.js"):root.TanDraftRecoveryVerifier,
  typeof module==="object"&&module.exports?require("./draft_legacy_writer.js"):root.TanDraftLegacyWriter);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftGuardedRecovery=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(legacy,verifier,writer){
 "use strict";
 const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
 async function restore({storage,locks,fetchFreshState,expectedRevision,reviewedCandidates,decision,confirmed}){
   if(confirmed!==true||!storage||typeof storage.getItem!=="function"||
      typeof storage.setItem!=="function"||!locks||
      typeof locks.request!=="function"||typeof fetchFreshState!=="function"||
      !decision||decision.choice!=="restore")
     return {status:"not_authorized"};
   try{
     return await locks.request(writer.LOCK_NAME,{mode:"exclusive"},async()=>{
       // The network read and local write occur under the same cooperative lock.
       // A remote change after this read cannot be prevented by a browser lock.
       let server;
       try{server=await fetchFreshState();}
       catch(_){return {status:"unavailable"};}
       const checked=verifier.verify({storage,serverState:server,expectedRevision,
         reviewedCandidates,decisions:[decision]});
       if(checked.status!=="ready_for_explicit_restore")return {status:checked.status};
       if(checked.accepted.length!==1)return {status:"invalid_request"};
       const item=checked.accepted[0],kind=item.kind,key=item.key;
       const storageKey=legacy.KEYS[kind];
       const before=legacy.read(storage);
       if(before.status!=="ready")return {status:before.status};
       if(own(before.snapshot[kind],key))return {status:"stale_local"};
       const raw=storage.getItem(storageKey);
       const next={...before.snapshot[kind],[key]:item.value};
       const encoded=JSON.stringify(next);
       // Fail closed on any uncoordinated mutation between validation and write.
       if(storage.getItem(storageKey)!==raw)return {status:"stale_local"};
       storage.setItem(storageKey,encoded);
       if(storage.getItem(storageKey)!==encoded)return {status:"uncertain_write"};
       return {status:"restored_under_cooperative_lock",kind,key};
     });
   }catch(_){return {status:"unavailable"};}
 }
 return {restore};
});
