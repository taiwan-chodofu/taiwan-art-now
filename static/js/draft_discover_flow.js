/* DRAFT ONLY: isolated Discover swipe/undo orchestration, not mounted.
 * Caller owns deck and rendering; skip never writes; never silently undoes
 * a changed item. Legacy tabs can still overwrite after the check.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
  ?require("./draft_page_controller.js"):root.TanDraftPageController);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftDiscoverFlow=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(page){
 "use strict";
 function create({storage,locks,normalizeKey,onAdvance,onRestore,onError}={}){
   const controller=page.create({storage,locks});
   const history=[];
   let pending=false;
   function valueFor(card,action){
     if(action==="like")return {title:card.title,museum:card.museum,dates:card.dates,
       url:card.detail_url,region:card.region,event:""};
     return {date:new Date().toISOString(),title:card.title,museum:card.museum,
       dates:card.dates,url:card.detail_url,region:card.region};
   }
   async function swipe(card,action){
     if(pending)return {status:"busy"};
     if(!card||!["like","visited","skip"].includes(action)||typeof normalizeKey!=="function")
       return {status:"invalid_request"};
     pending=true;
     try{
       let result={status:"skipped"};
       const key=normalizeKey(card.stable_key);
       if(action!=="skip"){
         const kind=action==="like"?"favs":"visited",value=valueFor(card,action);
         result=await controller.act({kind,key,action:"set",value});
         if(result.status!=="written_under_cooperative_lock"){
           if(typeof onError==="function")try{onError(result);}catch(_){}
           return result;
         }
         history.push({card,action,kind,key,value});
       }else history.push({card,action});
       if(typeof onAdvance==="function")try{onAdvance({card,action});}
         catch(_){return {status:"committed_ui_failed",writeStatus:result.status};}
       return result;
     }finally{pending=false;}
   }
   async function undo(){
     if(pending)return {status:"busy"};
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
     if(pending)return {status:'busy'};
     history.length=0;
     return {status:'cleared'};
   }
   return {swipe,undo,clearHistory,isBusy:()=>pending,historySize:()=>history.length};
 }
 return {create};
});
