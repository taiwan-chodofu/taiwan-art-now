/* DRAFT ONLY: shared read-only collection view model for Discover and My Page.
 * No bookmark writes. "Want to see" stays stored after "Seen" is marked.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
  ?require("./draft_exhibition_filters.js"):root.TanDraftExhibitionFilters);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftCollectionViewModel=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(filters){
 "use strict";
 function build({exhibitions,bookmarks,keyOf}={}){
  if(!Array.isArray(exhibitions)||typeof keyOf!=="function")
   return {status:"invalid_request"};
  const result={status:"ready",total:exhibitions.length,views:{}};
  for(const [name,filter] of Object.entries({
   watchlist:"watchlist",seen:"seen",discoverUnbookmarked:"unbookmarked",all:"all"
  })){
   const selection=filters.filterExhibitions(exhibitions,bookmarks,filter,keyOf);
   if(selection.status!=="ready")return {status:"invalid_request"};
   result.views[name]={items:selection.items,count:selection.items.length};
  }
  return result;
 }
 return {build};
});
