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
   heading:"已儲存到帳號，但這台裝置的清單有變動",
   detail:"展覽已成功儲存到帳號。不過，儲存期間這台裝置的「想看」或「看過」清單被其他分頁改動，兩邊的內容可能暫時不同。",
   action:"請先關閉其他開著的舊分頁，再到「想看」和「看過」清單核對展覽。先不要重複點選儲存，也不要清除瀏覽器資料。",
   requiresReview:true
  }),
  saved_server_local_review_required:Object.freeze({
   heading:"已儲存到帳號，但有展覽紀錄需要確認",
   detail:"這筆展覽已成功儲存到帳號，但這台裝置上原本的部分紀錄不見了或被更改。尚未確認哪些紀錄需要保留。",
   action:"請先關閉其他開著的舊分頁，保留目前頁面，並查看「想看」和「看過」清單。先不要重複儲存、刪除紀錄或清除瀏覽器資料。",
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
