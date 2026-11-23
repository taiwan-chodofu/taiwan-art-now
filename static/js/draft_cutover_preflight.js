/* DRAFT ONLY: read-only preflight gate for an explicitly initiated sync.
 * A checkpoint is a review signal, never proof of user deletion intent.
 * No network writes, localStorage writes, automatic recovery, or UI mount.
 */
(function(root,factory){
 const api=factory(
  typeof module==="object"&&module.exports?require("./draft_loss_detector.js"):root.TanDraftLossDetector,
  typeof module==="object"&&module.exports?require("./draft_authenticated_state.js"):root.TanDraftAuthenticatedState,
  typeof module==="object"&&module.exports?require("./draft_additive_merge.js"):root.TanDraftAdditiveMerge);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftCutoverPreflight=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(loss,auth,merge){
 "use strict";
 async function inspect({storage,checkpoint,fetchImpl}={}){
   if(!storage||typeof fetchImpl!=="function")
     return {status:"invalid_request",maySync:false};
   // A missing independent checkpoint is not evidence of safety.
   if(!checkpoint)return {status:"checkpoint_required",maySync:false};
   let report;
   try{report=loss.inspect({storage,checkpoint});}
   catch(_){return {status:"invalid_checkpoint",maySync:false};}
   if(report.status!=="consistent")
     return {status:"local_review_required",maySync:false,localStatus:report.status,
       missing:report.missing||[],changed:report.changed||[]};
   const remote=await auth.read({fetchImpl});
   if(remote.status!=="ready")
     return {status:remote.status,maySync:false};
   let proposal;
   try{proposal=merge.plan(storage,remote.state);}
   catch(_){return {status:"invalid_local",maySync:false};}
   if(proposal.status!=="prepared")
     return {status:proposal.status,maySync:false,review:proposal.review||[]};
   // Detect local writes that raced the authenticated GET.
   let after;
   try{after=loss.inspect({storage,checkpoint});}
   catch(_){return {status:"local_review_required",maySync:false};}
   if(after.status!=="consistent")
     return {status:"local_review_required",maySync:false,
       missing:after.missing||[],changed:after.changed||[]};
   return {status:"preflight_ready",maySync:true,
     base_revision:proposal.base_revision,
     proposedAdds:Object.keys(proposal.changes.favs).length+
       Object.keys(proposal.changes.visited).length,
     preservedRemote:proposal.preservedRemote.length,
     metadataDifferences:proposal.metadataDifferences.length,
     // Preflight is not a commit authorization or a lock on legacy tabs.
     requiresFreshCAS:true,requiresCoordinatedWriters:true};
 }
 return {inspect};
});
