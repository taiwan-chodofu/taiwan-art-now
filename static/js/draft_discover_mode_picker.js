/* DRAFT ONLY: accessible Discover mode selector; no bookmark mutations.
 * Caller updates its deck only after receiving a selected mode.
 */
(function(root,factory){
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.TanDraftDiscoverModePicker=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 const modes=["browse","unbookmarked"];
 const labels={
  zh:{browse:"探索展覽",unbookmarked:"只看尚未收藏",description:"「只看尚未收藏」會隱藏已加入「想去」或「已看」的展覽，不會刪除任何收藏。"},
  ja:{browse:"展示を探す",unbookmarked:"未登録だけを見る",description:"「未登録だけを見る」では「観たい」「観た」に登録した展示を非表示にします。登録は削除されません。"},
  en:{browse:"Explore exhibitions",unbookmarked:"Only not bookmarked",description:"This view hides exhibitions saved to Want or Seen. No bookmarks are removed."}
 };
 function mount({container,document:doc,lang="zh",mode="browse",onChange}={}){
  if(!container||!doc||typeof doc.createElement!=="function"||
     typeof onChange!=="function"||!modes.includes(mode))
   return {status:"invalid_request"};
  const words=labels[lang]||labels.zh;
  const group=doc.createElement("div");
  group.setAttribute("role","group");
  group.setAttribute("aria-label",words.browse);
  const buttons={};
  let selected=mode;
  for(const value of modes){
   const button=doc.createElement("button");
   button.setAttribute("type","button");
   button.textContent=words[value];
   button.setAttribute("aria-pressed",String(value===selected));
   button.addEventListener("click",()=>{
    if(value===selected)return;
    const accepted=onChange(value);
    if(accepted===false)return;
    selected=value;
    for(const key of modes)buttons[key].setAttribute("aria-pressed",String(key===selected));
   });
   buttons[value]=button;
   group.appendChild(button);
  }
  const description=doc.createElement("p");
  description.textContent=words.description;
  group.appendChild(description);
  container.replaceChildren(group);
  return {status:"mounted",getMode:()=>selected};
 }
 return {mount,labels};
});
