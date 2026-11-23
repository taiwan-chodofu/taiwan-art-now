/* DRAFT ONLY: accessible rendering of verified sync outcome.
 * Only changes a supplied container; never submits, reloads or clears data.
 */
(function(root,factory){
 const api=factory(typeof module==="object"&&module.exports
  ?require("./draft_save_outcome_copy.js"):root.TanDraftSaveOutcomeCopy);
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftSaveOutcomeNotice=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(copy){
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
  container.replaceChildren(notice);
  return {status:"rendered",requiresReview:message.requiresReview};
 }
 return {render};
});
