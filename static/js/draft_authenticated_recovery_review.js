/* DRAFT ONLY: authenticated read-only stale-tab recovery review.
 * Never writes to localStorage or server, never infers deletions from absence.
 * The server endpoint is not mounted in production.
 */
(function(root,factory){
 const api=factory(typeof module==='object'&&module.exports?require('./draft_authenticated_state.js'):root.TanDraftAuthenticatedState,
  typeof module==='object'&&module.exports?require('./draft_server_recovery.js'):root.TanDraftServerRecovery,
  typeof module==='object'&&module.exports?require('./draft_loss_detector.js'):root.TanDraftLossDetector);
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.TanDraftAuthenticatedRecoveryReview=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(auth,recovery,loss){
 'use strict';
 async function inspect({storage,fetchImpl,checkpoint}={}){
  if(!storage||typeof fetchImpl!=='function')return {status:'invalid_request',mayRestore:false};
  if(!checkpoint)return {status:'checkpoint_required',mayRestore:false};
  const before=loss.inspect({storage,checkpoint});
  if(before.status==='invalid_checkpoint'||before.status==='invalid_local'||before.status==='unavailable')
   return {status:before.status,mayRestore:false};
  const remote=await auth.read({fetchImpl});
  if(remote.status!=='ready')return {status:remote.status,mayRestore:false};
  const proposal=recovery.plan({storage,serverState:remote.state});
  if(!['prepared','needs_review'].includes(proposal.status))return {status:proposal.status,mayRestore:false};
  const after=loss.inspect({storage,checkpoint});
  if(JSON.stringify(before)!==JSON.stringify(after))return {status:'local_changed_during_review',mayRestore:false};
  return {status:'review_ready',mayRestore:false,base_revision:proposal.base_revision,
   localLoss:before.status==='needs_review',missingFromCheckpoint:before.missing,
   candidates:proposal.candidates,tombstoneConflicts:proposal.tombstoneConflicts,
   metadataDifferences:proposal.metadataDifferences,localOnly:proposal.localOnly,
   requiresExplicitRestoreConsent:true,requiresFreshAuthenticatedRead:true};
 }
 return {inspect};
});
