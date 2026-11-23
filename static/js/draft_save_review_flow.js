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
   ?require("./draft_save_outcome_notice.js"):root.TanDraftSaveOutcomeNotice,
  typeof module==="object"&&module.exports
   ?require("./draft_save_next_action.js"):root.TanDraftSaveNextAction);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftSaveReviewFlow=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(retry,verifier,notice,nextAction){
 "use strict";
 const REVIEW=new Set(["saved_server_local_changed",
  "saved_server_local_review_required"]);
 async function run({storage,fetchImpl,checkpoint,container,document:doc,exhibitionUrl}={}){
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
  // Never describe a specific exhibition as deleted when several unrelated
  // records failed verification. Their identities must be reviewed separately.
  const singleCommitted=result.committedChanges&&
   ["favs","visited"].reduce((n,kind)=>n+
    Object.keys(result.committedChanges[kind]||{}).length,0)===1;
  const specificReason=singleCommitted?reason:null;
  const recordStatus=specificReason==="deleted_on_server"?"saved_server_record_deleted"
   :specificReason==="different_server_value"?"saved_server_record_different"
   :singleCommitted?"saved_server_record_unconfirmed"
   :"saved_server_multiple_records_unconfirmed";
  const reviewItems=unresolved.map(item=>({kind:item.kind,key:item.key,reason:item.reason}));
  // Resolve display names from the exact committed payload, not an unrelated
  // current localStorage snapshot that may have been overwritten by old tabs.
  const trustedTitles=Object.create(null);
  for(const item of reviewItems){
   const change=result.committedChanges&&result.committedChanges[item.kind]&&
     Object.prototype.hasOwnProperty.call(result.committedChanges[item.kind],item.key)
     ?result.committedChanges[item.kind][item.key]:null;
   const value=change&&change.set;
   const title=value&&typeof value.title==="string"?value.title.trim():"";
   if(title)trustedTitles[item.kind+":"+item.key]=title;
  }
  // Caller titles are deliberately not used for unresolved records: stale
  // page data could label the wrong exhibition after a local overwrite.
  const displayResult=result.status==="saved_server_local_changed"&&
   verification&&verification.status==="confirmed_on_server"
    ?{...result,status:"saved_server_verified_local_changed"}
    :REVIEW.has(result.status)&&verification&&
      verification.status==="server_records_need_review"
      ?{...result,status:recordStatus,reviewItems,exhibitionTitles:trustedTitles}:result;
  const displayed=container&&doc
   ?notice.render({container,document:doc,result:displayResult}):null;
  // Only a verified deletion may offer a navigation link. The link never
  // performs a save or restores a tombstone; the user decides on the page.
  const action=displayed&&displayed.status==="rendered"&&container&&doc&&
    container.children&&container.children[0]
   ?nextAction.mount({container:container.children[0],document:doc,
      result:displayResult,exhibitionUrl}):null;
  return {result,verification,displayResult,displayed,action,reviewItems};
 }
 return {run};
});
