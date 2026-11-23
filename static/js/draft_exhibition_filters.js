/* DRAFT ONLY: exhibition bookmark presentation filters.
 * Both bookmarks are independent. Filtering never writes or deletes data.
 */
(function(root,factory){
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftExhibitionFilters=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
 function has(map,key){
  if(!map||typeof map!=="object"||Array.isArray(map)||!own(map,key))return false;
  const item=map[key];
  // Versioned server entries carry a deletion flag; legacy local entries
  // store values directly. Never infer a bookmark from a tombstone.
  if(item&&typeof item==="object"&&own(item,"deleted"))return item.deleted===false;
  return item!==null&&item!==undefined&&item!==false;
 }
 function classify(key,{favs,visited}={}){
  const want=has(favs,key),seen=has(visited,key);
  return {want,seen,watchlist:want&&!seen,seenList:seen,unbookmarked:!want&&!seen};
 }
 function matches(key,bookmarks,filter){
  const state=classify(key,bookmarks);
  if(filter==="watchlist")return state.watchlist;
  if(filter==="seen")return state.seenList;
  if(filter==="unbookmarked")return state.unbookmarked;
  if(filter==="all")return true;
  return false;
 }
 function filterExhibitions(exhibitions,bookmarks,filter="all",keyOf){
  if(!Array.isArray(exhibitions)||typeof keyOf!=="function")
   return {status:"invalid_request",items:[]};
  if(!["all","watchlist","seen","unbookmarked"].includes(filter))
   return {status:"invalid_filter",items:[]};
  return {status:"ready",items:exhibitions.filter(item=>{
   const key=keyOf(item);
   return typeof key==="string"&&key.length>0&&matches(key,bookmarks,filter);
  })};
 }
 return {classify,matches,filterExhibitions};
});
