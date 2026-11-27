/* DRAFT ONLY. Explicit, single-item restoration from a fresh authenticated GET.
 * Never mounted in production. Cached legacy tabs can still overwrite localStorage.
 */
(function(root,factory){
 const api=factory(typeof module==='object'&&module.exports?require('./draft_authenticated_state.js'):root.TanDraftAuthenticatedState,
  typeof module==='object'&&module.exports?require('./draft_guarded_recovery.js'):root.TanDraftGuardedRecovery);
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.TanDraftAuthenticatedGuardedRestore=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(auth,guarded){
 'use strict';
 async function restore({storage,locks,fetchImpl,expectedRevision,reviewedCandidates,decision,confirmed}={}){
  if(confirmed!==true||typeof fetchImpl!=='function'||!decision||decision.choice!=='restore')
   return {status:'not_authorized'};
  let readFailure=null;
  const result=await guarded.restore({storage,locks,expectedRevision,reviewedCandidates,decision,confirmed,
   fetchFreshState:async()=>{
    const response=await auth.read({fetchImpl});
    if(response.status!=='ready'){
     readFailure=response.status;
     throw Error('authenticated state unavailable');
    }
    return response.state;
   }});
  return readFailure?{status:readFailure}:result;
 }
 return {restore};
});
