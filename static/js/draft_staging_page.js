/* DRAFT ONLY: staging page lifecycle. No production template registration.
 * Fresh authenticated state owns every action descriptor and button state.
 */
(function(root,factory){
 const api=factory(typeof module==='object'&&module.exports
  ?require('./draft_authenticated_state.js'):root.TanDraftAuthenticatedState,
  typeof module==='object'&&module.exports
  ?require('./draft_server_button_bridge.js'):root.TanDraftServerButtonBridge);
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.TanDraftStagingPage=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(reader,bridge){
 'use strict';
 function create({win,fetchImpl,notice,lang='ja',items,onAnalytics}={}){
  if(!win||typeof fetchImpl!=='function'||!notice||!Array.isArray(items)||!items.length||
     !items.every(i=>i&&i.element&&typeof i.element.addEventListener==='function'&&
       ['favs','visited'].includes(i.kind)&&typeof i.key==='string'&&i.key&&
       i.value!==undefined&&i.value!==null&&!i.element.hasAttribute?.('onclick')&&
       typeof i.element.onclick!=='function')||
     new Set(items.map(i=>i.element)).size!==items.length)
   throw Error('invalid staging page');
  let current=null,closed=false,refreshGeneration=0;
  const message=(value)=>{notice.hidden=false;notice.textContent=value;notice.setAttribute('role','status');};
  const disable=()=>items.forEach(i=>{i.element.disabled=true;i.element.setAttribute('aria-disabled','true');});
  async function refresh(state){
   if(closed)return false;
   const generation=++refreshGeneration;
   disable();
   const latest=state?{status:'ready',state}:await reader.read({fetchImpl});
   if(closed||generation!==refreshGeneration)return false;
   if(latest.status!=='ready'){message(lang==='zh'?'無法確認最新收藏狀態，請重新整理頁面。':'最新の登録状況を確認できません。ページを再読み込みしてください。');return false;}
   if(!latest.state||!Number.isSafeInteger(latest.state.revision)||latest.state.revision<0||
      !latest.state.favs||typeof latest.state.favs!=='object'||
      !latest.state.visited||typeof latest.state.visited!=='object'){
     message(lang==='zh'?'無法確認最新收藏狀態，請重新整理頁面。':'最新の登録状況を確認できません。ページを再読み込みしてください。');return false;
   }
   const descriptors=items.map(item=>{
    const entry=latest.state[item.kind]?.[item.key];
    const active=!!entry&&!entry.deleted;
    const action=active?'remove':'set';
    item.element.setAttribute('aria-pressed',String(active));
    item.element.setAttribute('data-saved',String(active));
    return {element:item.element,kind:item.kind,key:item.key,action,
      value:action==='set'?item.value:undefined,expectedRevision:latest.state.revision};
   });
   if(current)current.dispose();
   if(closed)return false;
   current=bridge.mount({win,fetchImpl,notice,lang,buttons:descriptors,onAnalytics,
     onRefresh:async next=>{await refresh(next);}});
   items.forEach(i=>{i.element.disabled=false;i.element.removeAttribute('aria-disabled');});
   return true;
  }
  disable();
  let started=false;
  return {start:()=>{if(started||closed)return Promise.resolve(false);started=true;return refresh();},
   refresh:()=>started&&!closed?refresh():Promise.resolve(false),
   dispose:()=>{closed=true;refreshGeneration++;if(current)current.dispose();disable();}};
 }
 return {create};
});
