/* DRAFT ONLY: opt-in detail/Discover button bridge. Never mounted in production.
 * Callers supply explicit action and observed revision; no implicit toggle.
 */
(function(root,factory){
 const api=factory(typeof module==='object'&&module.exports?require('./draft_server_page_action.js'):root.TanDraftServerPageAction,
  typeof module==='object'&&module.exports?require('./draft_authenticated_state.js'):root.TanDraftAuthenticatedState);
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.TanDraftServerButtonBridge=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(page,stateApi){
 'use strict';
 const strings={
  ja:{busy:'保存中です…',success:'サーバーに保存しました。',stale_revision:'別の画面で登録が変更されました。ページを再読み込みして、ボタンの状態を確認してください。',deletion_review_required:'以前に削除した登録があります。ページを再読み込みして、登録内容を確認してください。',unauthorized:'登録状況を確認できません。ログイン状態を確認してから、ページを再読み込みしてください。',write_outcome_unknown:'保存できたか確認できませんでした。ページを再読み込みして登録状況を確認してください。確認するまではもう一度押さないでください。',fallback:'登録状況を確認できませんでした。ページを再読み込みして、ボタンの状態を確認してください。'},
  zh:{busy:'儲存中…',success:'已儲存至伺服器。',stale_revision:'其他頁面已更改收藏。請重新整理頁面，確認按鈕狀態。',deletion_review_required:'這筆收藏之前已刪除。請重新整理頁面，確認收藏狀態。',unauthorized:'無法確認收藏狀態。請確認登入狀態後重新整理頁面。',write_outcome_unknown:'無法確認是否儲存成功。請重新整理頁面確認收藏狀態；確認前請勿再次點擊。',fallback:'無法確認收藏狀態。請重新整理頁面，確認按鈕狀態。'}
 };
 function mount({win,fetchImpl,buttons,notice,lang='zh',onRender,onAnalytics,onRefresh,restoreImpl}={}){
  if(!win||typeof win.addEventListener!=='function'||typeof fetchImpl!=='function'||
    !notice||!Array.isArray(buttons)||buttons.length===0||
    !buttons.every(b=>b&&b.element&&typeof b.element.addEventListener==='function'&&
      ['favs','visited'].includes(b.kind)&&typeof b.key==='string'&&b.key&&
      ['set','remove'].includes(b.action)&&Number.isSafeInteger(b.expectedRevision)&&b.expectedRevision>=0&&
      (b.action!=='set'||(b.value!==null&&b.value!==undefined))&&
      !b.element.hasAttribute?.('onclick')&&typeof b.element.onclick!=='function'))
   throw Error('invalid staging mount');
  const locale=strings[lang]||strings.ja;
  let disposed=false,locked=false,inFlight=false,minimumRevision=0;
  const safe=(fn,v)=>{if(typeof fn==='function')try{fn(v);}catch(_){}};
  const show=(text)=>{if(disposed)return;notice.textContent=text;notice.hidden=false;notice.setAttribute?.('role','status');};
  const controller=page.create({fetchImpl,restoreImpl,onRender:x=>safe(onRender,x),onAnalytics:x=>safe(onAnalytics,x),
   onFailure:x=>show(locale[x.status]||locale.fallback),
   onBusy:({busy})=>{inFlight=busy;for(const b of buttons){b.element.disabled=busy||locked;b.element.setAttribute?.('aria-busy',String(busy));}if(busy)show(locale.busy);}});
  const handlers=[];
  for(const b of buttons){
   const handler=async()=>{if(disposed||locked||inFlight)return;
    const result=await controller.act({kind:b.kind,key:b.key,action:b.action,value:b.value,expectedRevision:b.expectedRevision,tombstoneRevision:b.tombstoneRevision});
    if(!disposed&&(result.status==='write_outcome_unknown'||result.status==='stale_revision'||result.status==='review_expired'||result.committed===true)){
      // Every button in this mounted snapshot shares a revision. After any
      // confirmed write (or uncertain outcome), none may reuse that revision.
      // Require a fresh authoritative GET and a new mount before further edits.
      minimumRevision=result.committed?result.revision:b.expectedRevision+1;
      locked=true;
      for(const item of buttons){
        item.element.disabled=true;
        item.element.setAttribute?.('aria-disabled','true');
      }
    }
    const unknown=result.status==='write_outcome_unknown';
    const stale=result.status==='stale_revision'||result.status==='review_expired';
    if(disposed||(!unknown&&!stale&&!result.committed))return;
    if(result.committed)show(locale.success);
    if(typeof onRefresh!=='function')return;
    if(unknown||stale)show(lang==='zh'?'正在確認目前的收藏狀態…':'現在の登録状況を確認しています…');
    try{
      const latest=await stateApi.read({fetchImpl});
      if(disposed)return;
      // Once the revision advances, the original CAS can no longer take effect.
      // A matching value still cannot identify which device wrote it.
      const usable=latest.status==='ready'&&latest.state.revision>=minimumRevision;
      if(!usable){show(unknown?locale.write_outcome_unknown:locale.fallback);return;}
      if(unknown||stale){
        const label=(lang==='zh'?{favs:'想看',visited:'看過'}:{favs:'観たい',visited:'観た'})[b.kind];
        const entry=latest.state[b.kind][b.key];
        const active=!!entry&&!entry.deleted;
        show(lang==='zh'
          ?(active?'這個展覽目前已加入「':'這個展覽目前未加入「')+label+'」。'
          :'この展示は現在「'+label+'」に'+(active?'登録されています。':'登録されていません。'));
      }
      await onRefresh(latest.state);
    }catch(_){if(!disposed)show(unknown?locale.write_outcome_unknown:locale.fallback);}

   };
   b.element.addEventListener('click',handler);handlers.push([b.element,handler]);
  }
  const dispose=()=>{if(disposed)return;disposed=true;controller.dispose();for(const [el,fn] of handlers)el.removeEventListener('click',fn);win.removeEventListener('pagehide',onPageHide);};
  const onPageHide=event=>{if(!event.persisted)dispose();};
  win.addEventListener('pagehide',onPageHide);
  return {dispose,isBusy:()=>inFlight,minimumRevision:()=>minimumRevision};
 }
 return {mount};
});
