/* DRAFT ONLY. Server-first authenticated CAS writer; never mutates localStorage.
 * No automatic retry, no optimistic success, no production mounting.
 */
(function(root,factory){
 const api=factory(typeof module==='object'&&module.exports
  ?require('./draft_authenticated_state.js'):root.TanDraftAuthenticatedState);
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.TanDraftAuthenticatedWriter=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(auth){
 'use strict';
 const PATH='/api/private-subscribers/v2/changes';
 const validKey=k=>typeof k==='string'&&k.length>0&&k.length<=512;
 async function commit({fetchImpl,kind,key,action,value,expectedRevision,isActive=()=>true}={}){
  if(typeof fetchImpl!=='function'||!['favs','visited'].includes(kind)||
    !validKey(key)||!['set','remove'].includes(action)||
    !Number.isSafeInteger(expectedRevision)||expectedRevision<0||
    (action==='set'&&(value===null||value===undefined)))
    return {status:'invalid_request',committed:false};
  // A fresh authenticated read is required. The caller's revision is only a
  // conflict guard; never replace it silently with a newer revision.
  const current=await auth.read({fetchImpl});
  if(!isActive())return {status:'disposed',committed:false};
  if(current.status!=='ready')return {status:current.status,committed:false};
  if(current.state.revision!==expectedRevision)
    return {status:'stale_revision',committed:false};
  const existing=current.state[kind][key];
  if(action==='set'&&existing&&existing.deleted)
    return {status:'deletion_review_required',committed:false};
  if(action==='remove'&&(!existing||existing.deleted))
    return {status:'already_absent',committed:false};
  const changes={favs:{},visited:{}};
  changes[kind][key]=action==='set'?{set:value}:{delete:true};
  let response;
  try{response=await fetchImpl(PATH,{method:'POST',credentials:'same-origin',
    cache:'no-store',redirect:'error',mode:'same-origin',
    headers:{'Accept':'application/json','Content-Type':'application/json'},
    body:JSON.stringify({base_revision:expectedRevision,changes})});}
  catch(_){return {status:'write_outcome_unknown',committed:false};}
  if(!response)return {status:'write_outcome_unknown',committed:false};
  if(response.status===409)return {status:'stale_revision',committed:false};
  if(response.status===401||response.status===403)
    return {status:'unauthorized',committed:false};
  if(!response.ok)return {status:'write_outcome_unknown',committed:false};
  const type=response.headers?.get?.('content-type');
  const cache=response.headers?.get?.('cache-control');
  if(!type||!/^application\/json(?:\s*;|\s*$)/i.test(type)||
    !cache||!/(?:^|,)\s*no-store\b/i.test(cache))
    return {status:'write_outcome_unknown',committed:false};
  let written;
  try{written=await response.json();}catch(_){return {status:'write_outcome_unknown',committed:false};}
  // Response alone is not proof of durability; verify via fresh GET.
  const confirmed=await auth.read({fetchImpl});
  if(confirmed.status!=='ready')return {status:'write_outcome_unknown',committed:false};
  const entry=confirmed.state[kind][key];
  if(!entry||entry.revision<=expectedRevision||
    (action==='set'&&(entry.deleted||!auth.sameJson(entry.value,value)))||
    (action==='remove'&&!entry.deleted))
    return {status:'write_outcome_unknown',committed:false};
  if(!written||written.revision!==confirmed.state.revision)
    return {status:'write_outcome_unknown',committed:false};
  return {status:'server_confirmed',committed:true,revision:confirmed.state.revision};
 }
 return {commit,PATH};
});
