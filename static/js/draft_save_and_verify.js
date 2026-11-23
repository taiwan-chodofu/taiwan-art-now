/* DRAFT ONLY: automatically read back a confirmed save when legacy local data drifted.
 * Read-only verification; never retries a write or alters localStorage.
 */
(function(root,factory){
 const api=factory(
  typeof module==="object"&&module.exports?require("./draft_additive_retry.js"):root.TanDraftAdditiveRetry,
  typeof module==="object"&&module.exports?require("./draft_post_save_verify.js"):root.TanDraftPostSaveVerify);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftSaveAndVerify=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(additive,verifier){
 "use strict";
 async function run(options={}){
  const saved=await additive.run(options);
  if(!saved||!saved.serverSaved||!saved.committedChanges||
     !["saved_server_local_changed","saved_server_local_review_required"].includes(saved.status))
   return saved;
  const verified=await verifier.verify({
   fetchImpl:options.fetchImpl,committedRevision:saved.revision,
   changes:saved.committedChanges
  });
  // Keep the original confirmed-commit result and its local warning.
  // A later GET failure or concurrent deletion must never erase that evidence.
  return {...saved,verification:verified};
 }
 return {run};
});
