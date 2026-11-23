/* DRAFT ONLY: shared server-first page action for Discover and detail.
 * Explicit set/remove only: toggle requires an authoritative current state.
 * No localStorage writes, legacy notification calls, or template mounting.
 */
(function(root,factory){
 const api=factory(typeof module==='object'&&module.exports
  ?require('./draft_authenticated_writer.js'):root.TanDraftAuthenticatedWriter);
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.TanDraftServerPageAction=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(writer){
 'use strict';
 function create({fetchImpl,onRender,onAnalytics,onFailure,onBusy}={}){
  if(typeof fetchImpl!=='function')throw Error('authenticated fetch required');
  const pending=new Set();let disposed=false;
  const safe=(fn,value)=>{if(!disposed&&typeof fn==='function')try{fn(value);}catch(_){}};
  async function act({kind,key,action,value,expectedRevision}={}){
   if(disposed)return {status:'disposed',committed:false};
   const slot=kind+':'+key;
   if(pending.has(slot))return {status:'busy',committed:false};
   pending.add(slot);safe(onBusy,{kind,key,busy:true});
   try{
    const result=await writer.commit({fetchImpl,kind,key,action,value,expectedRevision});
    if(result.committed===true&&result.status==='server_confirmed'){
     safe(onRender,{kind,key,action,revision:result.revision});
     safe(onAnalytics,{kind,key,action,event:kind==='visited'
      ?(action==='set'?'mark_visited':'unmark_visited')
      :(action==='set'?'add_to_favorites':'remove_from_favorites')});
    }else safe(onFailure,{kind,key,action,status:result.status});
    return result;
   }catch(_){const result={status:'write_outcome_unknown',committed:false};
    safe(onFailure,{kind,key,action,status:result.status});return result;
   }finally{pending.delete(slot);safe(onBusy,{kind,key,busy:false});}
  }
  return {act,dispose:()=>{disposed=true;},isBusy:(kind,key)=>pending.has(kind+':'+key)};
 }
 return {create};
});
