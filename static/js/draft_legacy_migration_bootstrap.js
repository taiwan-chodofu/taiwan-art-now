/* DRAFT ONLY: orchestrates the one-time legacy localStorage -> authenticated
 * server migration. Not mounted in any template yet. Ties together three
 * already-independent, already-tested pieces without duplicating their logic:
 *   - draft_legacy_candidate_policy.js: classifies which legacy entries are
 *     safe to silently add (truly absent server-side) vs need a human
 *     decision (server holds an explicit tombstone for that key).
 *   - draft_authenticated_writer.js: the same CAS writer every other screen
 *     already uses for a single-key write.
 *   - draft_migration_review.js: the human-facing explanation of exactly one
 *     case -- a locally-present item the server explicitly deleted
 *     elsewhere. Every other difference is silently resolved in the
 *     server's favor; this is the only one surfaced to the user.
 * run() never retries an uncertain/stale write automatically -- a stale
 * revision mid-batch stops the batch so the caller can re-run from a fresh
 * read, matching the "no automatic retry on uncertain outcomes" convention
 * used everywhere else in this codebase.
 */
(function(root,factory){
 const api=factory(
  typeof module==="object"&&module.exports?require("./draft_legacy_snapshot.js"):root.TanDraftLegacySnapshot,
  typeof module==="object"&&module.exports?require("./draft_legacy_candidate_policy.js"):root.TanDraftLegacyCandidatePolicy,
  typeof module==="object"&&module.exports?require("./draft_migration_review.js"):root.TanDraftMigrationReview,
  typeof module==="object"&&module.exports?require("./draft_authenticated_state.js"):root.TanDraftAuthenticatedState,
  typeof module==="object"&&module.exports?require("./draft_authenticated_writer.js"):root.TanDraftAuthenticatedWriter);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftLegacyMigrationBootstrap=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(legacySnapshot,policy,review,auth,writer){
 "use strict";
 function create({fetchImpl,storage,restoreImpl}={}){
  let disposed=false;
  async function run(lang="ja"){
   if(disposed)return {status:"disposed"};
   if(typeof fetchImpl!=="function"||!storage)return {status:"invalid_request"};
   const snapshot=legacySnapshot.read(storage);
   if(snapshot.status!=="ready")return {status:snapshot.status,kind:snapshot.kind};
   const hasLocalData=Object.keys(snapshot.snapshot.favs).length>0||
    Object.keys(snapshot.snapshot.visited).length>0;
   if(!hasLocalData)return {status:"nothing_to_migrate"};
   let current=await auth.read({fetchImpl});
   if(disposed)return {status:"disposed"};
   if(current.status!=="ready")return {status:current.status};
   const classified=policy.classify({legacy:snapshot.snapshot,server:current.state});
   if(classified.status!=="classified")return {status:"invalid_local"};
   let submitted=0,revision=classified.base_revision;
   for(const item of classified.adds){
    if(disposed)return {status:"disposed",submitted};
    const result=await writer.commit({fetchImpl,kind:item.kind,key:item.key,
     action:"set",value:item.value,expectedRevision:revision,isActive:()=>!disposed});
    if(!result.committed)return {status:"partial",submitted,failure:result.status};
    submitted++;
    revision=result.revision;
   }
   if(disposed)return {status:"disposed",submitted};
   // Re-read once more so the review reflects whatever is now actually on
   // the server (the adds just submitted, plus anything another device may
   // have changed concurrently) rather than the pre-batch snapshot.
   const after=await auth.read({fetchImpl});
   const reportState=after.status==="ready"?after.state:current.state;
   const report=review.preview(storage,reportState);
   return {status:"ready",submitted,revision:reportState.revision,
    review:review.explain(report,lang)};
  }
  async function resolveReviewItem({kind,key,choice}={}){
   if(disposed)return {status:"disposed",committed:false};
   if(choice!=="request_restore")return {status:"kept_deleted",committed:false};
   const snapshot=legacySnapshot.read(storage);
   if(snapshot.status!=="ready")return {status:snapshot.status,committed:false};
   const value=snapshot.snapshot[kind]&&snapshot.snapshot[kind][key];
   if(value===undefined)return {status:"not_found_locally",committed:false};
   const current=await auth.read({fetchImpl});
   if(disposed)return {status:"disposed",committed:false};
   if(current.status!=="ready")return {status:current.status,committed:false};
   const entry=current.state[kind]&&current.state[kind][key];
   if(!entry||!entry.deleted)return {status:"review_expired",committed:false};
   if(typeof restoreImpl!=="function")return {status:"not_applicable",committed:false};
   return restoreImpl({fetchImpl,kind,key,value,reviewedRevision:current.state.revision,
    tombstoneRevision:entry.revision,confirmed:true,isActive:()=>!disposed});
  }
  return {run,resolveReviewItem,dispose:()=>{disposed=true;}};
 }
 return {create};
});
