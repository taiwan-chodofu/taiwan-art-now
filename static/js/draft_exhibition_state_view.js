/* DRAFT ONLY: accessible read-only exhibition save-state presentation.
 * No storage mutation, POST, or automatic restoration.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
  ?require("./draft_exhibition_current_state.js"):root.TanDraftExhibitionCurrentState);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftExhibitionStateView=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(current){
 "use strict";
 function describe(result){
  if(!result)return {heading:"目前無法確認收藏狀態",detail:"請稍後再試。"};
  if(result.status==="saved"){
   const labels=(result.collections||[]).map(k=>k==="favs"?"想看":"看過");
   return {heading:"已收藏",detail:"這筆展覽目前已加入："+labels.join("、")};
  }
  if(result.status==="removed")
   return {heading:"目前未收藏",detail:"這筆展覽先前已從收藏清單移除。若想再次收藏，請自行選擇「想看」或「看過」。"};
  if(result.status==="not_found")
   return {heading:"目前未收藏",detail:"目前的帳號清單中沒有這筆展覽。若想收藏，可以自行選擇「想看」或「看過」。"};
  return {heading:"目前無法確認收藏狀態",detail:"暫時無法取得最新收藏資料。請稍後再試，不需要連續點選收藏。"};
 }
 async function show({container,document:doc,fetchImpl,exhibitionKey}={}){
  if(!container||!doc||typeof doc.createElement!=="function")
   return {status:"invalid_request"};
  const result=await current.check({fetchImpl,exhibitionKey});
  const message=describe(result);
  const section=doc.createElement("section");
  section.setAttribute("role","status");
  section.setAttribute("aria-live","polite");
  const title=doc.createElement("h2");
  title.textContent=message.heading;
  const detail=doc.createElement("p");
  detail.textContent=message.detail;
  section.appendChild(title);
  section.appendChild(detail);
  container.replaceChildren(section);
  return {status:"rendered",result};
 }
 return {show,describe};
});
