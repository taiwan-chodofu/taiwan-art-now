/* DRAFT ONLY: user-facing Taiwan Mandarin copy for confirmed server commits.
 * Pure presentation mapping. Does not reload, retry, mutate storage or fetch.
 */
(function(root,factory){
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftSaveOutcomeCopy=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 const MESSAGES=Object.freeze({
  saved:Object.freeze({
   heading:"已儲存",
   detail:"這筆展覽已儲存到你的帳號。",
   action:"可以繼續瀏覽展覽。",
   requiresReview:false
  }),
  saved_server_local_changed:Object.freeze({
   heading:"展覽已成功儲存",
   detail:"這筆展覽已保存在你的帳號中，但目前的清單可能沒有顯示最新內容。",
   action:"如果還開著其他 Taiwan Art Now 頁面，請先關閉那些頁面，再回到這裡查看「想看」或「看過」清單。不需要再次儲存。",
   requiresReview:true
  }),
  saved_server_local_review_required:Object.freeze({
   heading:"展覽已成功儲存，其他紀錄需要確認",
   detail:"這筆展覽已保存在你的帳號中。不過，先前儲存的其他展覽可能沒有出現在目前的清單中。",
   action:"請保留這個頁面。如果還開著其他 Taiwan Art Now 頁面，請先關閉那些頁面，再回來查看「想看」和「看過」清單。確認前請不要刪除紀錄。",
   requiresReview:true
  }),
  unknown_commit:Object.freeze({
   heading:"目前無法確認是否儲存成功",
   detail:"送出後沒有收到可靠的儲存結果，因此不能判定成功或失敗。",
   action:"請先查看帳號中的「想看」或「看過」清單，確認這筆展覽是否已存在。確認前請不要連續點選儲存。",
   requiresReview:true
  })
 });
 function forResult(result){
  if(!result||typeof result.status!=="string")return null;
  const message=MESSAGES[result.status];
  if(!message)return null;
  if(result.status.startsWith("saved_server_")&&result.serverSaved!==true)return null;
  return {...message,status:result.status};
 }
 return {forResult};
});
