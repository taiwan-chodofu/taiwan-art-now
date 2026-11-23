/* DRAFT ONLY: run GET-only verification after confirmed save with local drift.
 * Never retries the POST, repairs storage, or masks a server verification failure.
 */
(function(root,factory){
 const api=factory(
  typeof module==="object"&&module.exports
   ?require("./draft_additive_retry.js"):root.TanDraftAdditiveRetry,
  typeof module==="object"&&module.exports
   ?require("./draft_post_save_verify.js"):root.TanDraftPostSaveVerify,
  typeof module==="object"&&module.exports
   ?require("./draft_save_outcome_notice.js"):root.TanDraftSaveOutcomeNotice);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftSaveReviewFlow=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(retry,verifier,notice){
 "use strict";
 const REVIEW=new Set(["saved_server_local_changed",
  "saved_server_local_review_required"]);
 async function run({storage,fetchImpl,checkpoint,container,document:doc}={}){
  const result=await retry.run({storage,fetchImpl,checkpoint});
  let verification=null;
  if(REVIEW.has(result.status)&&result.serverSaved===true){
   verification=await verifier.verify({
    fetchImpl,committedRevision:result.revision,
    changes:result.committedChanges
   });
  }
  // A verified committed exhibition can be shown as a calm success, but a
  // missing trusted checkpoint still needs separate review of other records.
  const unresolved=verification&&verification.status==="server_records_need_review"
   ?verification.unresolved||[]:[];
  const reason=unresolved.length===1?unresolved[0].reason:null;
  const recordStatus=reason==="deleted_on_server"?"saved_server_record_deleted"
   :reason==="different_server_value"?"saved_server_record_different"
   :"saved_server_record_unconfirmed";
  const displayResult=result.status==="saved_server_local_changed"&&
   verification&&verification.status==="confirmed_on_server"
    ?{...result,status:"saved_server_verified_local_changed"}
    :REVIEW.has(result.status)&&verification&&
      verification.status==="server_records_need_review"
      ?{...result,status:recordStatus}:result;
  const displayed=container&&doc
   ?notice.render({container,document:doc,result:displayResult}):null;
  return {result,verification,displayResult,displayed};
 }
 return {run};
});
