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
 async function read({fetchImpl}){
   if(typeof fetchImpl!=="function")return {status:"invalid_request"};
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
   try{state=await response.json();sync.validateServer(state);}
   catch(_){return {status:"invalid_server"};}
   return {status:"ready",state};
 }
 return {read,PATH};
});
