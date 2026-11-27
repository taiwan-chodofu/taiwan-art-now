/* DRAFT ONLY: accessible rendering of verified sync outcome.
 * Only changes a supplied container; never submits, reloads or clears data.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
  ?require("./draft_save_outcome_copy.js"):root.TanDraftSaveOutcomeCopy,
  typeof module==="object"&&module.exports
  ?require("./draft_save_next_action.js"):root.TanDraftSaveNextAction);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftSaveOutcomeNotice=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(copy,nextAction){
 "use strict";
 function render({container,document:doc,result}={}){
  if(!container||!doc||typeof doc.createElement!=="function")
   return {status:"invalid_request"};
  const message=copy.forResult(result);
  if(!message)return {status:"unsupported_result"};
  // Build first: an invalid result must not clear an existing warning.
  const notice=doc.createElement("section");
  notice.setAttribute("role",message.requiresReview?"alert":"status");
  notice.setAttribute("aria-live",message.requiresReview?"assertive":"polite");
  notice.setAttribute("aria-atomic","true");
  notice.setAttribute("data-draft-save-outcome",message.status);
  const heading=doc.createElement("h2");
  heading.textContent=message.heading;
  const detail=doc.createElement("p");
  detail.textContent=message.detail;
  const action=doc.createElement("p");
  action.textContent=message.action;
  notice.appendChild(heading);
  notice.appendChild(detail);
  notice.appendChild(action);
  if(message.status==="saved_server_multiple_records_unconfirmed"&&
     Array.isArray(result.reviewItems)&&result.reviewItems.length){
   const list=doc.createElement("ul");
   for(const item of result.reviewItems){
    const row=doc.createElement("li");
    // Internal identifiers are not meaningful exhibition names. A trusted
    // title must be supplied by the calling view; never display raw keys.
    const title=result.exhibitionTitles&&
      Object.prototype.hasOwnProperty.call(result.exhibitionTitles,item.kind+":"+item.key)
      ?result.exhibitionTitles[item.kind+":"+item.key]:null;
    const name=typeof title==="string"&&title.trim()
      ?title:"名稱未提供的展覽";
    const heading=doc.createElement("strong");
    heading.textContent=name;
    const state=doc.createElement("span");
    state.textContent=item.reason==="deleted_on_server"
      ?"目前已從清單移除"
      :item.reason==="different_server_value"
       ?"目前的收藏內容與剛才不同"
       :"目前無法確認是否仍在清單中";
    row.appendChild(heading);
    row.appendChild(state);
    const itemUrl=result.exhibitionUrls&&
      Object.prototype.hasOwnProperty.call(result.exhibitionUrls,item.kind+":"+item.key)
      ?result.exhibitionUrls[item.kind+":"+item.key]:null;
    if(nextAction&&typeof nextAction.isSafeExhibitionUrl==="function"&&
       nextAction.isSafeExhibitionUrl(itemUrl)){
     const link=doc.createElement("a");
     link.setAttribute("href",itemUrl);
     link.textContent="查看這筆展覽";
     link.setAttribute("aria-label","查看展覽："+name+"，確認目前的收藏狀態");
     row.appendChild(link);
    }
    list.appendChild(row);
   }
   notice.appendChild(list);
  }
  container.replaceChildren(notice);
  return {status:"rendered",requiresReview:message.requiresReview};
 }
 return {render};
});
