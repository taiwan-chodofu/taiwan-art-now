/* DRAFT ONLY: opt-in detail/Discover button bridge. Never mounted in production.
 * Callers supply explicit action and observed revision; no implicit toggle.
 */
(function(root,factory){
 const api=factory(typeof module==='object'&&module.exports?require('./draft_server_page_action.js'):root.TanDraftServerPageAction);
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.TanDraftServerButtonBridge=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(page){
 'use strict';
 const strings={
  ja:{busy:'保存中です…',success:'サーバーに保存しました。',stale_revision:'別の画面で登録が変更されました。ページを再読み込みして、ボタンの状態を確認してください。',deletion_review_required:'以前に削除した登録があります。ページを再読み込みして、登録内容を確認してください。',unauthorized:'登録状況を確認できません。ログイン状態を確認してから、ページを再読み込みしてください。',write_outcome_unknown:'保存できたか確認できませんでした。ページを再読み込みして登録状況を確認してください。確認するまではもう一度押さないでください。',fallback:'登録状況を確認できませんでした。ページを再読み込みして、ボタンの状態を確認してください。'},
  zh:{busy:'儲存中…',success:'已儲存至伺服器。',stale_revision:'其他頁面已更改收藏。請重新整理頁面，確認按鈕狀態。',deletion_review_required:'這筆收藏之前已刪除。請重新整理頁面，確認收藏狀態。',unauthorized:'無法確認收藏狀態。請確認登入狀態後重新整理頁面。',write_outcome_unknown:'無法確認是否儲存成功。請重新整理頁面確認收藏狀態；確認前請勿再次點擊。',fallback:'無法確認收藏狀態。請重新整理頁面，確認按鈕狀態。'}
 };
 function mount({win,fetchImpl,buttons,notice,lang='zh',onRender,onAnalytics}={}){
  if(!win||typeof win.addEventListener!=='function'||typeof fetchImpl!=='function'||
    !notice||!Array.isArray(buttons)||buttons.length===0||
    !buttons.every(b=>b&&b.element&&typeof b.element.addEventListener==='function'&&
      ['favs','visited'].includes(b.kind)&&typeof b.key==='string'&&b.key&&
      ['set','remove'].includes(b.action)&&Number.isSafeInteger(b.expectedRevision)&&b.expectedRevision>=0&&
      (b.action!=='set'||(b.value!==null&&b.value!==undefined))&&
      !b.element.hasAttribute?.('onclick')&&typeof b.element.onclick!=='function'))
   throw Error('invalid staging mount');
  const locale=strings[lang]||strings.ja;
  let disposed=false;
  const safe=(fn,v)=>{if(typeof fn==='function')try{fn(v);}catch(_){}};
  const show=(text)=>{if(disposed)return;notice.textContent=text;notice.hidden=false;notice.setAttribute?.('role','status');};
  const controller=page.create({fetchImpl,onRender:x=>safe(onRender,x),onAnalytics:x=>safe(onAnalytics,x),
   onFailure:x=>show(locale[x.status]||locale.fallback),
   onBusy:({kind,key,busy})=>{for(const b of buttons)if(b.kind===kind&&b.key===key){b.element.disabled=busy;b.element.setAttribute?.('aria-busy',String(busy));}if(busy)show(locale.busy);}});
  const handlers=[];
  for(const b of buttons){
   const handler=async()=>{if(disposed)return;
    const result=await controller.act({kind:b.kind,key:b.key,action:b.action,value:b.value,expectedRevision:b.expectedRevision});
    if(!disposed&&result.status==='write_outcome_unknown'){
      // Never invite a blind repeat after a request may have reached the server.
      b.element.disabled=true;
      b.element.setAttribute?.('aria-disabled','true');
    }
    if(!disposed&&result.committed===true){show(locale.success);
      // A later click must use a newly rendered state and revision.
      b.element.disabled=true;
      b.element.setAttribute?.('aria-disabled','true');
    }
   };
   b.element.addEventListener('click',handler);handlers.push([b.element,handler]);
  }
  const dispose=()=>{if(disposed)return;disposed=true;controller.dispose();for(const [el,fn] of handlers)el.removeEventListener('click',fn);win.removeEventListener('pagehide',dispose);};
  win.addEventListener('pagehide',dispose,{once:true});
  return {dispose};
 }
 return {mount};
});
