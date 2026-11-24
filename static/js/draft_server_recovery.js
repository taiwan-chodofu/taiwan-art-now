/* DRAFT ONLY: server-to-local recovery proposal, strictly read-only.
 * A verified server response is a dependency supplied by caller; this module
 * does not authenticate, write, restore, or infer deletion from local absence.
 */
(function(root,factory) {
  const api=factory(typeof module==="object"&&module.exports
    ? require("./draft_legacy_snapshot.js"):root.TanDraftLegacySnapshot,
    typeof module==="object"&&module.exports
    ? require("./draft_versioned_sync.js"):root.TanDraftSync);
  if(typeof module==="object"&&module.exports)module.exports=api;
  else root.TanDraftServerRecovery=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(legacy,sync){
  "use strict";
  const own=(obj,key)=>Object.prototype.hasOwnProperty.call(obj,key);
  function plan({storage,serverState}) {
    const local=legacy.read(storage);
    if(local.status!=="ready")return {status:local.status,kind:local.kind};
    try {sync.plan(local.snapshot,serverState);}
    catch(_){return {status:"invalid_server"};}
    const candidates=[],tombstoneConflicts=[],metadataDifferences=[],localOnly=[];
    for(const kind of ["favs","visited"]){
      for(const [key,remote] of Object.entries(serverState[kind])){
        const present=own(local.snapshot[kind],key);
        if(remote.deleted){
          if(present)tombstoneConflicts.push({kind,key,reason:"explicit_deletion_conflict",
            item_revision:remote.revision});
          continue;
        }
        // Validate the server value as a legitimate legacy record. An active
        // remote entry with invalid shape must never be offered for restoration.
        let value;
        try {value=legacy.validateMap({[key]:remote.value},kind)[key];}
        catch(_){return {status:"invalid_server_value",kind,key};}
        if(!present)candidates.push({kind,key,value,item_revision:remote.revision});
        else if(!sync.sameJson(value,local.snapshot[kind][key]))
          metadataDifferences.push({kind,key,reason:"metadata_diff_preserved"});
      }
      for(const key of Object.keys(local.snapshot[kind]))
        if(!own(serverState[kind],key))localOnly.push({kind,key});
    }
    return {status:tombstoneConflicts.length?"needs_review":"prepared",
      base_revision:serverState.revision,candidates,tombstoneConflicts,
      metadataDifferences,localOnly,requiresExplicitRestoreConsent:true};
  }
  return {plan};
});
