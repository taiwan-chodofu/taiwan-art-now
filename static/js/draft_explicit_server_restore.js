/* DRAFT ONLY: explicit server tombstone restoration, never mounted in production.
 * Requires reviewed exact tombstone revision, user confirmation, fresh authenticated
 * GET, single-key CAS POST, then another authenticated GET to verify durability.
 * An uncertain POST outcome is NEVER retried automatically.
 */
(function(root,factory){
 const api=factory(typeof module==='object'&&module.exports
  ?require('./draft_authenticated_state.js'):root.TanDraftAuthenticatedState,
  typeof module==='object'&&module.exports?require('./draft_explicit_keep.js'):root.TanDraftExplicitKeep);
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.TanDraftExplicitServerRestore=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(auth,keep){
 'use strict';
 const validKey=k=>typeof k==='string'&&k.length>0&&k.length<=512&&
  !['__proto__','constructor','prototype'].includes(k);
 async function restore({fetchImpl,kind,key,value,reviewedRevision,tombstoneRevision,
  confirmed}={}){
  if(confirmed!==true||typeof fetchImpl!=='function'||
   !['favs','visited'].includes(kind)||!validKey(key)||
   value===undefined||value===null||
   !Number.isSafeInteger(reviewedRevision)||reviewedRevision<1||
   !Number.isSafeInteger(tombstoneRevision)||tombstoneRevision<1)
   return {status:'not_authorized',committed:false};
  const current=await auth.read({fetchImpl});
  if(current.status!=='ready')return {status:current.status,committed:false};
  const entry=current.state[kind][key];
  if(current.state.revision!==reviewedRevision||!entry||!entry.deleted||
   entry.revision!==tombstoneRevision)
   return {status:'review_expired',committed:false};
  let failure='confirmation_unavailable',written;
  async function request(path,payload){
   if(path.endsWith('/consume'))failure='write_outcome_unknown';
   const response=await fetchImpl(path,{
    method:'POST',credentials:'same-origin',cache:'no-store',redirect:'error',mode:'same-origin',
    headers:{'Accept':'application/json','Content-Type':'application/json'},body:JSON.stringify(payload)
   });
   if(response?.status===409)failure='review_expired';
   if(response?.status===401||response?.status===403)failure='unauthorized';
   if(!response?.ok||!/^application\/json(?:\s*;|\s*$)/i.test(response.headers?.get?.('content-type')||'')||
      !/(?:^|,)\s*no-store\b/i.test(response.headers?.get?.('cache-control')||''))
    throw Error('Invalid confirmation response');
   return response.json();
  }
  try{
   const result=await keep.execute({
    decision:{kind,key,choice:'keep_saved'},
    conflict:{kind,key,itemRevision:tombstoneRevision,reason:'explicit_deletion_conflict'},
    localValue:value,baseRevision:reviewedRevision,request
   });
   if(result.status!=='submitted')return {status:failure,committed:false};
   written=result.state;
  }catch(_){return {status:failure,committed:false};}
  const verified=await auth.read({fetchImpl});
  if(verified.status!=='ready')return {status:'write_outcome_unknown',committed:false};
  const saved=verified.state[kind][key];
  if(!saved||saved.deleted||saved.revision<=tombstoneRevision||
   JSON.stringify(saved.value)!==JSON.stringify(value)||
   verified.state.revision!==written?.revision)
   return {status:'write_outcome_unknown',committed:false};
  return {status:'server_confirmed',committed:true,revision:verified.state.revision};
 }
 return {restore};
});
