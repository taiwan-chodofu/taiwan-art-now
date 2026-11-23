/* DRAFT ONLY: opt-in server recovery review UI. No writes or network.
 * This UI is for remote-active/local-absent candidates, NOT tombstone conflicts.
 */
(function(root,factory){
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftRecoveryUI=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 function createReview(container,report,doc){
   if(!container||!doc||typeof doc.createElement!=="function"||
      !report||!["prepared","needs_review"].includes(report.status)||
      !Array.isArray(report.candidates)||
      report.requiresExplicitRestoreConsent!==true)
     throw new Error("Invalid recovery report");
   const decisions=new Map();
   const seen=new Set();
   for(const item of report.candidates){
     if(!item||!["favs","visited"].includes(item.kind)||
       typeof item.key!=="string"||!item.key||
       !Number.isSafeInteger(item.item_revision)||item.item_revision<1)
       throw new Error("Invalid recovery candidate");
     const id=JSON.stringify([item.kind,item.key]);
     if(seen.has(id))throw new Error("Duplicate recovery candidate");
     seen.add(id);
   }
   if(!report.candidates.length)
     return {rendered:false,getDecisions:()=>[],dispose:()=>{}};
   const section=doc.createElement("section");
   section.setAttribute("aria-label","保存記録の復旧候補");
   const heading=doc.createElement("h2");
   heading.textContent="別の端末に残っている展示";
   section.appendChild(heading);
   const intro=doc.createElement("p");
   intro.textContent="現在の端末にない保存記録が見つかりました。復元する展示を選んでください。何も選ばなければ変更しません。";
   section.appendChild(intro);
   for(const item of report.candidates){
     const id=JSON.stringify([item.kind,item.key]);
     const wrap=doc.createElement("div");
     const prompt=doc.createElement("p");
     const title=typeof item.value==="object"&&item.value&&typeof item.value.title==="string"
       ? item.value.title:item.key;
     prompt.textContent=title+(item.kind==="favs"?"（観たい）":"（観た）");
     wrap.appendChild(prompt);
     const select=doc.createElement("select");
     select.setAttribute("aria-label",title+" の復元");
     for(const [value,label] of [["decide_later","あとで決める"],["restore","この端末にも復元する"]]){
       const option=doc.createElement("option");
       option.value=value;option.textContent=label;select.appendChild(option);
     }
     decisions.set(id,"decide_later");
     select.addEventListener("change",()=>{
       if(select.value==="restore"||select.value==="decide_later")
         decisions.set(id,select.value);
     });
     wrap.appendChild(select);section.appendChild(wrap);
   }
   const note=doc.createElement("p");
   note.textContent="選択内容はまだ保存されません。復元前に最新の記録を再確認します。";
   section.appendChild(note);container.appendChild(section);
   return {rendered:true,getDecisions:()=>Array.from(decisions,([id,choice])=>{
     const [kind,key]=JSON.parse(id);return {kind,key,choice};
   }),dispose:()=>section.remove()};
 }
 return {createReview};
});
