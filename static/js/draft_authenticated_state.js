/* DRAFT ONLY: strict same-origin authenticated state reader.
 * Does not infer identity, write, cache, retry, or register a route.
 * Server session ownership is enforced by the unregistered Flask endpoint.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
   ? require("./draft_versioned_sync.js"):root.TanDraftSync);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftAuthenticatedState=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(sync){
 "use strict";
 const PATH="/api/private-subscribers/v2/state";
 const trustedWorkers=new WeakSet();
 async function supportsPrivateReads(worker){
   if(!worker||trustedWorkers.has(worker))return true;
   if(typeof MessageChannel!=="function")return false;
   const marker="tan-private-network-only-v1";
   return new Promise(resolve=>{
     const channel=new MessageChannel();
     const finish=ok=>{
       clearTimeout(timer);
       channel.port1.close();
       if(ok)trustedWorkers.add(worker);
       resolve(ok);
     };
     const timer=setTimeout(()=>finish(false),1500);
     channel.port1.onmessage=e=>finish(e.data===marker);
     try{worker.postMessage(marker,[channel.port2]);}
     catch(_){channel.port2.close();finish(false);}
   });
 }
 async function read({fetchImpl,serviceWorker=globalThis.navigator?.serviceWorker}){
   if(typeof fetchImpl!=="function")return {status:"invalid_request"};
   const controller=serviceWorker?.controller;
   if(controller&&(!await supportsPrivateReads(controller)||serviceWorker?.controller!==controller))
     return {status:"worker_update_required"};
   let response;
   try{response=await fetchImpl(PATH,{method:"GET",credentials:"same-origin",
     cache:"no-store",redirect:"error",mode:"same-origin",
     headers:{"Accept":"application/json"}});}
   catch(_){return {status:"unavailable"};}
   if(!response)return {status:"unavailable"};
   if(response.status===401||response.status===403)return {status:"unauthorized"};
   if(!response.ok)return {status:"unavailable"};
   // A login redirect, HTML response or cacheable response must never be
   // interpreted as an authenticated, current subscriber state.
   const contentType=response.headers&&typeof response.headers.get==="function"
     ? response.headers.get("content-type"):null;
   const cacheControl=response.headers&&typeof response.headers.get==="function"
     ? response.headers.get("cache-control"):null;
   if(!contentType||!/^application\/json(?:\s*;|\s*$)/i.test(contentType)||
      !cacheControl||!/(?:^|,)\s*no-store\b/i.test(cacheControl))
     return {status:"invalid_response"};
   let state;
   try{state=await response.json();sync.plan({favs:{},visited:{}},state);}
   catch(_){return {status:"invalid_server"};}
   if(serviceWorker?.controller!==controller)return {status:"worker_update_required"};
   return {status:"ready",state};
 }
 return {read,PATH};
});
