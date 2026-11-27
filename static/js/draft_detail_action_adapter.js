/* DRAFT ONLY: isolated detail-page action orchestration. NOT mounted in templates.
 * Analytics, UI rendering and legacy notification sync follow verified persistence.
 * Does not authenticate the legacy notification endpoint or fix cached-tab races.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
   ?require("./draft_page_controller.js"):root.TanDraftPageController);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftDetailActionAdapter=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(controller){
 "use strict";
 function create({storage,locks,key,metadata,onRender,onAnalytics,onNotify,onFailure,onBusy,now}={}){
   const clock=typeof now==="function"?now:()=>new Date().toISOString();
   let disposed=false;
   const live=(fn,arg)=>{if(!disposed)safe(fn,arg);};
   const safe=(fn,arg)=>{if(typeof fn==="function")try{fn(arg);}catch(_){}};
   const ctrl=controller.create({storage,locks,onBusy:x=>live(onBusy,x),
     onCommitted:({kind,action})=>{
       live(onRender,{kind,action});
       live(onAnalytics,{kind,action,event:kind==="visited"
         ?(action==="set"?"mark_visited":"unmark_visited")
         :(action==="set"?"add_to_favorites":"remove_from_favorites")});
       live(onNotify,{kind,action});
     },
     onFailure:({kind,status})=>live(onFailure,{kind,status})
   });
   async function toggle(kind){
     if(disposed)return {status:"disposed"};
     if(!["visited","favs"].includes(kind)||typeof key!=="string"||!key)
       return {status:"invalid_request"};
     // Values are supplied for a possible set; the writer decides toggle direction
     // from freshly read storage inside the exclusive cooperative lock.
     const value=kind==="visited"?clock():metadata;
     return ctrl.act({kind,key,action:"toggle",value});
   }
   return {toggle,isBusy:ctrl.isBusy,dispose:()=>{disposed=true;}};
 }
 return {create};
});
