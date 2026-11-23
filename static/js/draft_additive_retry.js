/* DRAFT ONLY. Additive CAS retry after one stale revision; never mounted.
 * No local writes, no silent tombstone restoration, no unbounded retries.
 */
(function(root,factory){
  const api=factory(
    typeof module==="object"&&module.exports
      ? require("./draft_authenticated_state.js"):root.TanDraftAuthenticatedState,
    typeof module==="object"&&module.exports
      ? require("./draft_additive_merge.js"):root.TanDraftAdditiveMerge,
    typeof module==="object"&&module.exports
      ? require("./draft_legacy_snapshot.js"):root.TanDraftLegacySnapshot,
    typeof module==="object"&&module.exports
      ? require("./draft_versioned_sync.js"):root.TanDraftSync,
    typeof module==="object"&&module.exports
      ? require("./draft_loss_detector.js"):root.TanDraftLossDetector);
  if(typeof module==="object"&&module.exports)module.exports=api;
  else root.TanDraftAdditiveRetry=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(reader,merge,legacy,sync,loss){
  "use strict";
  const PATH="/api/private-subscribers/v2/changes";
  const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
  const hasChanges=c=>["favs","visited"].some(k=>Object.keys(c[k]).length>0);
  const stable=x=>JSON.stringify(x);
  function checkCheckpoint(storage,checkpoint){
    if(!checkpoint)return null;
    try{
      const result=loss.inspect({storage,checkpoint});
      return result.status==="consistent"?null:{status:"local_review_required",
        localStatus:result.status,missing:result.missing||[],changed:result.changed||[]};
    }catch(_){return {status:"local_review_required"};}
  }
  async function run({storage,fetchImpl,checkpoint}={}){
    if(!storage||typeof fetchImpl!=="function")return {status:"invalid_request"};
    const initialLoss=checkCheckpoint(storage,checkpoint);
    if(initialLoss)return initialLoss;
    const original=legacy.read(storage);
    if(original.status!=="ready")return {status:original.status};
    const initialSnapshot=stable(original.snapshot);
    let retried=false;
    for(let attempt=0;attempt<2;attempt++){
      const beforeGet=checkCheckpoint(storage,checkpoint);
      if(beforeGet)return beforeGet;
      const latest=await reader.read({fetchImpl});
      if(latest.status!=="ready")return {status:latest.status};
      const afterGet=checkCheckpoint(storage,checkpoint);
      if(afterGet)return afterGet;
      const local=legacy.read(storage);
      if(local.status!=="ready")return {status:local.status};
      if(stable(local.snapshot)!==initialSnapshot)return {status:"local_changed"};
      const proposal=merge.plan(storage,latest.state);
      if(proposal.status!=="prepared")
        return {status:proposal.status,review:proposal.review||[]};
      if(!hasChanges(proposal.changes))
        return {status:"up_to_date",revision:proposal.base_revision,retried,
          preservedRemote:proposal.preservedRemote,
          metadataDifferences:proposal.metadataDifferences};
      // A second read guards against local mutations between planning and POST.
      const beforePost=legacy.read(storage);
      if(beforePost.status!=="ready")return {status:beforePost.status};
      if(stable(beforePost.snapshot)!==initialSnapshot)return {status:"local_changed"};
      const beforeSend=checkCheckpoint(storage,checkpoint);
      if(beforeSend)return beforeSend;
      let response;
      try{
        response=await fetchImpl(PATH,{
          method:"POST",credentials:"same-origin",cache:"no-store",
          redirect:"error",mode:"same-origin",
          headers:{"Content-Type":"application/json","Accept":"application/json"},
          body:JSON.stringify({base_revision:proposal.base_revision,changes:proposal.changes})
        });
      }catch(_){return {status:"unknown_commit"};}
      if(!response)return {status:"unknown_commit"};
      if(response.status===409){
        if(attempt===1)return {status:"stale_revision"};
        retried=true;
        continue;
      }
      if(response.status===401||response.status===403)return {status:"unauthorized"};
      if(!response.ok)return {status:"unavailable"};
      let saved;
      try{
        const ct=response.headers&&response.headers.get("content-type");
        const cc=response.headers&&response.headers.get("cache-control");
        if(!ct||!/^application\/json(?:\s*;|\s*$)/i.test(ct)||
           !cc||!/(?:^|,)\s*no-store\b/i.test(cc))
          return {status:"unknown_commit"};
        saved=await response.json();
        sync.plan({favs:{},visited:{}},saved);
        if(saved.revision!==proposal.base_revision+1)return {status:"unknown_commit"};
        for(const kind of ["favs","visited"]){
          for(const [key,change] of Object.entries(proposal.changes[kind])){
            const item=saved[kind][key];
            if(!item||item.deleted||!own(item,"value")||
               stable(item.value)!==stable(change.set))
              return {status:"unknown_commit"};
          }
        }
      }catch(_){return {status:"unknown_commit"};}
      return {status:"saved",revision:saved.revision,retried,
        preservedRemote:proposal.preservedRemote,
        metadataDifferences:proposal.metadataDifferences};
    }
    return {status:"stale_revision"};
  }
  return {run,PATH};
});
