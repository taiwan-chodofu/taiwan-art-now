/* DRAFT ONLY. Classify a legacy candidate against authenticated server state.
 * No writes. A legacy absence is NEVER a deletion intent.
 * This module must not be mounted as a production migration without review.
 */
(function(root,factory){
  const api=factory();
  if(typeof module==="object"&&module.exports)module.exports=api;
  else root.TanDraftLegacyCandidatePolicy=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
  "use strict";
  const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
  function classify({legacy,server}={}){
    if(!legacy||!server||typeof legacy!=="object"||typeof server!=="object"||
       !Number.isSafeInteger(server.revision)||server.revision<1)
      return {status:"invalid_input",adds:[],reviews:[]};
    const adds=[],reviews=[];
    for(const kind of ["favs","visited"]){
      if(!legacy[kind]||!server[kind]||
         typeof legacy[kind]!=="object"||Array.isArray(legacy[kind])||
         typeof server[kind]!=="object"||Array.isArray(server[kind]))
        return {status:"invalid_input",adds:[],reviews:[]};
      for(const key of Object.keys(legacy[kind])){
        if(!key||["__proto__","constructor","prototype"].includes(key))
          return {status:"invalid_input",adds:[],reviews:[]};
        if(!own(server[kind],key)){
          adds.push({kind,key,value:legacy[kind][key]});
        }else if(server[kind][key]&&server[kind][key].deleted===true){
          reviews.push({kind,key,reason:"server_tombstone"});
        }
        // Existing server values are authoritative; no metadata overwrite.
      }
    }
    return {status:"classified",adds,reviews,base_revision:server.revision,
      requiresServerCAS:true};
  }
  return {classify};
});
