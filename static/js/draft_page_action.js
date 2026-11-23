/* DRAFT ONLY: shared action entrypoint for home, Discover, nearby, detail.
 * No production template mounts it. No server calls, legacy ref, or tombstones.
 * Toggle direction is decided inside the writer's cooperative Web Lock.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
   ?require("./draft_legacy_writer.js"):root.TanDraftLegacyWriter);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftPageAction=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(writer){
 "use strict";
 async function commit({storage,locks,kind,key,action,value,onCommitted,onFailure}={}){
   if(!storage||!locks||!["favs","visited"].includes(kind)||
     typeof key!=="string"||!key||!["toggle","set","remove"].includes(action))
     return {status:"invalid_request"};
   const result=await writer.mutate({storage,locks,kind,key,action,value});
   if(result.status==="written_under_cooperative_lock"){
     if(typeof onCommitted==="function"){
       try{onCommitted({kind,key,action:result.action});}
       catch(_){return {status:"committed_callback_failed",action:result.action};}
     }
   }else if(result.status!=="unchanged"&&typeof onFailure==="function"){
     try{onFailure(result);}catch(_){}
   }
   return result;
 }
 return {commit};
});
