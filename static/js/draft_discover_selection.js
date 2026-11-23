/* DRAFT ONLY: read-only Discover deck selection using shared bookmark rules.
 * Default Discover keeps wanted items discoverable, but excludes Seen.
 * Explicit unbookmarked mode excludes both bookmarks. Never writes.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
  ?require("./draft_exhibition_filters.js"):root.TanDraftExhibitionFilters);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftDiscoverSelection=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(filters){
 "use strict";
 function select({cards,bookmarks,normalizeKey,mode="browse"}={}){
  if(!Array.isArray(cards)||typeof normalizeKey!=="function"||
     !bookmarks||typeof bookmarks!=="object")return {status:"invalid_request",cards:[]};
  if(!["browse","unbookmarked","watchlist","seen"].includes(mode))
   return {status:"invalid_mode",cards:[]};
  const selected=[];
  for(const card of cards){
   if(!card||typeof card.stable_key!=="string")continue;
   const key=normalizeKey(card.stable_key);
   if(typeof key!=="string"||!key)continue;
   const state=filters.classify(key,bookmarks);
   const include=mode==="browse"?!state.seen:
    mode==="unbookmarked"?state.unbookmarked:
    mode==="watchlist"?state.watchlist:state.seen;
   if(include)selected.push(card);
  }
  return {status:"ready",cards:selected};
 }
 return {select};
});
