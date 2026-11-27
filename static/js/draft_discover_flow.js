/* DRAFT ONLY: isolated Discover swipe/undo orchestration, not mounted.
 * Caller owns deck and rendering; skip never writes; never silently undoes
 * a changed item. Legacy tabs can still overwrite after the check.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
  ?require("./draft_page_controller.js"):root.TanDraftPageController,
  typeof module==="object"&&module.exports?require("./draft_authenticated_state.js"):root.TanDraftAuthenticatedState,
  typeof module==="object"&&module.exports?require("./draft_authenticated_writer.js"):root.TanDraftAuthenticatedWriter);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftDiscoverFlow=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(page,reader,writer){
 "use strict";
 function create({storage,locks,normalizeKey,onAdvance,onRestore,onError,fetchImpl,restoreImpl}={}){
   const localController=fetchImpl?null:page.create({storage,locks});
   let uncertain=false,uncertainSinceRevision=null,disposed=false;
   const createdRevisions=new Map();
   const controller={act:async intent=>{
     if(!fetchImpl)return localController.act(intent);
     if(uncertain)return {status:"unknown_commit"};
     const latest=await reader.read({fetchImpl});
     if(latest.status!=="ready")return {status:latest.status};
     const entry=latest.state[intent.kind][intent.key];
     const slot=JSON.stringify([intent.kind,intent.key]);
     if(intent.action==="set_if_absent"&&entry&&!entry.deleted)return {status:"unchanged"};
     if(intent.action==="remove_if_equal"&&(!entry||entry.deleted||
        entry.revision!==createdRevisions.get(slot)||!reader.sameJson(entry.value,intent.expectedValue)))
       return {status:"stale_undo"};
     const result=await writer.commit({fetchImpl,kind:intent.kind,key:intent.key,
       action:intent.action==="set_if_absent"?"set":"remove",value:intent.value,
       expectedRevision:latest.state.revision});
     if(result.status==="write_outcome_unknown"){uncertain=true;uncertainSinceRevision=latest.state.revision;}
     if(!result.committed)return result;
     if(intent.action==="set_if_absent")createdRevisions.set(slot,result.revision);
     else createdRevisions.delete(slot);
     return {status:"written_under_cooperative_lock",revision:result.revision};
   }};
   const history=[];
   let pending=false;
   function valueFor(card,action){
     if(action==="like")return {title:card.title,museum:card.museum,dates:card.dates,
       url:card.detail_url,region:card.region,event:""};
     return {date:new Date().toISOString(),title:card.title,museum:card.museum,
       dates:card.dates,url:card.detail_url,region:card.region};
   }
   async function swipe(card,action){
     if(disposed)return {status:"disposed"};
     if(pending)return {status:"busy"};
     if(uncertain)return {status:"unknown_commit"};
     if(!card||!["like","visited","skip"].includes(action)||typeof normalizeKey!=="function")
       return {status:"invalid_request"};
     pending=true;
     try{
       let result={status:"skipped"};
       const key=normalizeKey(card.stable_key);
       if(action!=="skip"){
         const kind=action==="like"?"favs":"visited",value=valueFor(card,action);
         result=await controller.act({kind,key,action:"set_if_absent",value});
         if(result.status==="deletion_review_required"){
           // A prior removal (possibly from another device) tombstoned this
           // item; a blind set is never allowed to resurrect it. Advance the
           // deck instead of getting stuck, but do not claim it was saved.
           // The card-only history entry (no kind/key/value) means undo just
           // restores the card, matching the "unchanged" shape below; the
           // caller may call confirmRestore(card,action) later to resurrect
           // it explicitly, which pushes its own live history entry on success.
           history.push({card,action});
           result={status:"needs_restore_review",kind,key};
         }else if(result.status!=="written_under_cooperative_lock"&&result.status!=="unchanged"){
           if(typeof onError==="function")try{onError(result);}catch(_){}
           return result;
         }else if(result.status==="unchanged"){
           history.push({card,action});
           result={status:"skipped",preservedExisting:true};
         }else history.push({card,action,kind,key,value});
       }else history.push({card,action});
       if(typeof onAdvance==="function")try{onAdvance({card,action});}
         catch(_){return {status:"committed_ui_failed",writeStatus:result.status};}
       return result;
     }finally{pending=false;}
   }
   async function undo(){
     if(disposed)return {status:"disposed"};
     if(pending)return {status:"busy"};
     if(uncertain)return {status:"unknown_commit"};
     if(!history.length)return {status:"nothing_to_undo"};
     pending=true;
     try{
       const last=history[history.length-1];
       let result={status:"skipped"};
       if(last.kind){
         result=await controller.act({kind:last.kind,key:last.key,
           action:"remove_if_equal",expectedValue:last.value});
         if(result.status!=="written_under_cooperative_lock"){
           if(typeof onError==="function")try{onError(result);}catch(_){}
           return result;
         }
       }
       history.pop();
       if(typeof onRestore==="function")try{onRestore(last);}
         catch(_){return {status:"committed_ui_failed",writeStatus:result.status};}
       return result;
     }finally{pending=false;}
   }
   function clearHistory(){
     if(disposed)return {status:'disposed'};
     if(pending)return {status:'busy'};
     history.length=0;
     return {status:'cleared'};
   }
   function lastUndoTarget(){
     const last=history[history.length-1];
     return last&&last.kind?{kind:last.kind,key:last.key,title:last.card.title}:null;
   }
   async function recover(){
     // Mirrors the detail/nearby recovery rule: a fresh authenticated read
     // only clears the lock once global revision has moved past the
     // uncertain write's own base revision. An unchanged revision leaves
     // open the possibility of a delayed write, so stay locked and never
     // replay the mutation (see DECISIONS.md 2026-11-24).
     if(disposed)return {status:"disposed"};
     if(pending)return {status:"busy"};
     if(!fetchImpl)return {status:"not_applicable"};
     if(!uncertain)return {status:"not_uncertain"};
     pending=true;
     try{
       const latest=await reader.read({fetchImpl});
       if(latest.status!=="ready")return {status:latest.status};
       if(latest.state.revision<=uncertainSinceRevision)return {status:"still_unknown_commit"};
       uncertain=false;uncertainSinceRevision=null;
       return {status:"recovered",revision:latest.state.revision};
     }finally{pending=false;}
   }
   async function confirmRestore(card,action){
     // The only path that may resurrect a tombstone, and only on an explicit
     // caller-initiated call (never from swipe/undo itself). Mirrors detail's
     // explicit restore: a fresh read supplies both the global revision and
     // the item's exact tombstone revision, which the server re-verifies.
     if(disposed)return {status:"disposed"};
     if(pending)return {status:"busy"};
     if(uncertain)return {status:"unknown_commit"};
     if(!fetchImpl||typeof restoreImpl!=="function")return {status:"not_applicable"};
     if(!card||!["like","visited"].includes(action)||typeof normalizeKey!=="function")
       return {status:"invalid_request"};
     pending=true;
     try{
       const key=normalizeKey(card.stable_key),kind=action==="like"?"favs":"visited";
       const latest=await reader.read({fetchImpl});
       if(latest.status!=="ready")return {status:latest.status};
       const entry=latest.state[kind][key];
       if(!entry||!entry.deleted)return {status:"not_tombstoned"};
       const value=valueFor(card,action);
       const result=await restoreImpl({fetchImpl,kind,key,value,
         reviewedRevision:latest.state.revision,tombstoneRevision:entry.revision,
         confirmed:true,isActive:()=>!disposed});
       if(result.status==="write_outcome_unknown"){uncertain=true;uncertainSinceRevision=latest.state.revision;}
       if(!result.committed){
         if(typeof onError==="function")try{onError(result);}catch(_){}
         return result;
       }
       createdRevisions.set(JSON.stringify([kind,key]),result.revision);
       history.push({card,action,kind,key,value});
       if(typeof onAdvance==="function")try{onAdvance({card,action,restored:true});}
         catch(_){return {status:"committed_ui_failed",writeStatus:result.status};}
       return {status:"written_under_cooperative_lock",revision:result.revision};
     }finally{pending=false;}
   }
   function dispose(){disposed=true;}
   return {swipe,undo,clearHistory,recover,dispose,confirmRestore,lastUndoTarget,
     isBusy:()=>pending,isUncertain:()=>uncertain,historySize:()=>history.length};
 }
 return {create};
});
