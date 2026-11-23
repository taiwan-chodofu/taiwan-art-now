/* DRAFT ONLY: page-facing busy/error adapter for four legacy views.
 * Does not mount, alter DOM, send analytics or notification requests.
 * A caller must defer its own visual state transitions until committed.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
   ?require("./draft_page_action.js"):root.TanDraftPageAction);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftPageController=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(actions){
 "use strict";
 function create({storage,locks,onBusy,onCommitted,onFailure}={}){
   const pending=new Set();
   async function act({kind,key,action,value,expectedValue}={}){
     if(!["favs","visited"].includes(kind)||typeof key!=="string"||!key)
       return {status:"invalid_request"};
     const slot=kind+":"+key;
     if(pending.has(slot))return {status:"busy"};
     pending.add(slot);
     try{
       if(typeof onBusy==="function"){
         try{onBusy({kind,key,busy:true});}catch(_){
           return {status:"ui_callback_failed"};
         }
       }
       const result=await actions.commit({storage,locks,kind,key,action,value,expectedValue});
       if(result.status==="written_under_cooperative_lock"){
         if(typeof onCommitted==="function"){
           try{onCommitted({kind,key,action:result.action});}
           catch(_){return {status:"committed_callback_failed",action:result.action};}
         }
       }else if(result.status!=="unchanged"&&typeof onFailure==="function"){
         try{onFailure({kind,key,status:result.status});}catch(_){}
       }
       return result;
     }finally{
       pending.delete(slot);
       if(typeof onBusy==="function")try{onBusy({kind,key,busy:false});}catch(_){}
     }
   }
   return {act,isBusy:(kind,key)=>pending.has(kind+":"+key)};
 }
 return {create};
});
