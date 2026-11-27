/* DRAFT ONLY: mode switching for Discover without losing card order.
 * Caller supplies the full original ordered deck; changes never write bookmarks.
 * Switching modes clears stale swipe-undo history via a caller callback.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
  ?require("./draft_discover_selection.js"):root.TanDraftDiscoverSelection);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftDiscoverModeSession=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(selection){
 "use strict";
 function create({cards,bookmarks,normalizeKey,onModeChanged,canChange}={}){
  if(!Array.isArray(cards)||!bookmarks||typeof normalizeKey!=="function")
   return {status:"invalid_request"};
  let mode="browse";
  let source=cards.slice();
  function visible(){
   return selection.select({cards:source,bookmarks,normalizeKey,mode});
  }
  function change(next){
   if(next===mode)return {status:"unchanged",...visible()};
   if(typeof canChange==="function"&&!canChange())
    return {status:"busy",cards:visible().cards};
   const check=selection.select({cards:source,bookmarks,normalizeKey,mode:next});
   if(check.status!=="ready")return check;
   const previous=mode;
   mode=next;
   if(typeof onModeChanged==="function")onModeChanged({previous,mode});
   return {status:"ready",mode,cards:check.cards};
  }
  function update({cards:nextCards,bookmarks:nextBookmarks}={}){
   if(Array.isArray(nextCards))source=nextCards.slice();
   if(nextBookmarks&&typeof nextBookmarks==="object")bookmarks=nextBookmarks;
   return visible();
  }
  return {status:"ready",change,visible,update,getMode:()=>mode};
 }
 return {create};
});
