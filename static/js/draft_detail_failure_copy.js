/* DRAFT ONLY: actionable detail bookmark failure messages. No automatic retries. */
(function(root,factory){
 const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.TanDraftDetailFailureCopy=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const copy={
  ja:{unavailable:'保存できませんでした。端末の空き容量やブラウザの保存設定を確認してから、もう一度ボタンを押してください。',
      not_authorized:'保存できませんでした。このページを通常のブラウザで開き直して、もう一度ボタンを押してください。',
      conflict:'保存状態が変わった可能性があります。ページを再読み込みし、ボタンの状態を確認してから操作してください。',
      fallback:'保存できたか確認できませんでした。ページを再読み込みしてボタンの状態を確認してください。確認するまでは繰り返し押さないでください。'},
  zh:{unavailable:'無法儲存。請確認裝置儲存空間與瀏覽器的儲存設定，再按一次按鈕。',
      not_authorized:'無法儲存。請用一般瀏覽器重新開啟此頁面，再按一次按鈕。',
      conflict:'儲存狀態可能已變更。請重新整理頁面，確認按鈕狀態後再操作。',
      fallback:'目前無法確認是否儲存成功。請重新整理頁面，確認按鈕狀態；確認前請勿重複點擊。'},
  en:{unavailable:'Could not save. Check your device storage and browser storage settings, then press the button again.',
      not_authorized:'Could not save. Reopen this page in a regular browser, then press the button again.',
      conflict:'Your saved status may have changed. Reload this page and check the button before trying again.',
      fallback:'Could not confirm whether this was saved. Reload this page and check the button. Do not press it again until you have checked.'}
 };
 function message(status,lang){const locale=copy[lang]||copy.ja;return locale[status]||locale.fallback;}
 return {message};
});
