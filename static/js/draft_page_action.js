/* DRAFT ONLY: one async per-exhibition action entrypoint for four templates.
 * No template is mounted. Never trusts a stale UI map for toggle direction.
 * Web Locks protect only cooperating tabs; cached legacy tabs remain unsafe.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
   ?require("./draft_legacy_writer.js"):root.TanDraftLegacyWriter,
   typeof module==="object"&&module.exports
   ?require("./draft_legacy_snapshot.js"):root.TanDraftLegacySnapshot);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftPageAction=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(writer,legacy){
 "use strict";
 const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
 async function commit({storage,locks,kind,key,action,value,onCommitted,onFailure}={}){
   if(!storage||!locks||!["favs","visited"].includes(kind)||
     typeof key!=="string"||!key||!["toggle","set","remove"].includes(action))
     return {status:"invalid_request"};
   try{
     return await locks.request(writer.LOCK_NAME,{mode:"exclusive"},async()=>{
       const current=legacy.read(storage);
       if(current.status!=="ready")return {status:current.status};
       const exists=own(current.snapshot[kind],key);
       const resolved=action==="toggle"?(exists?"remove":"set"):action;
       if(resolved==="set"){
         if(value===undefined)return {status:"missing_value"};
         legacy.validateMap({[key]:value},kind);
       }
       // Writer obtains the same lock, so use its per-item operation only
       // after this outer lock exits: no nested Web Lock deadlock.
       return {status:"planned",resolved,existed:exists};
     }).then(async planned=>{
       if(planned.status!=="planned")return planned;
       // Rechecking under the writer lock is required: planning may be stale.
       // Explicit set/remove is safe, but toggle needs an atomic decision.
       if(action==="toggle")return {status:"toggle_requires_atomic_writer"};
       const result=await writer.mutate({storage,locks,kind,key,action,value});
       if(result.status==="written_under_cooperative_lock"&&typeof onCommitted==="function")
         try{onCommitted({kind,key,action});}catch(_){return {status:"committed_callback_failed"};}
       else if(result.status!=="written_under_cooperative_lock"&&
         result.status!=="unchanged"&&typeof onFailure==="function")
         try{onFailure(result);}catch(_){}
       return result;
     });
   }catch(_){return {status:"unavailable"};}
 }
 return {commit};
});
