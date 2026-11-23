/* DRAFT ONLY: read-only migration decision display. No writes or automatic restore.
 * The host must separately recheck authenticated state before any restoration.
 */
(function(root,factory){
 const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.TanDraftSimpleReviewUI=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 function mount({container,doc,review,onDecision}={}){
  if(!container||!doc||typeof doc.createElement!=='function'||!review||
    review.status!=='ready'||review.mayWrite!==false||!Array.isArray(review.items))
   throw Error('invalid review');
  const section=doc.createElement('section');
  section.setAttribute('aria-label','登録の確認');
  const choices=[];
  for(const item of review.items){
   if(!item||item.status!=='deleted_remotely'||!['favs','visited'].includes(item.kind)||
      typeof item.key!=='string'||!item.key||!Array.isArray(item.options)||
      item.options.length!==2||item.options[0].id!=='keep_deleted'||
      item.options[1].id!=='request_restore')throw Error('invalid review item');
   const block=doc.createElement('div');
   const heading=doc.createElement('h3');heading.textContent=item.title;block.appendChild(heading);
   const message=doc.createElement('p');message.textContent=item.message;block.appendChild(message);
   const select=doc.createElement('select');
   select.setAttribute('aria-label',item.title);
   for(const choice of item.options){
    const option=doc.createElement('option');option.value=choice.id;
    option.textContent=choice.label;select.appendChild(option);
   }
   select.value='keep_deleted';
   select.addEventListener('change',()=>{
    if(select.value!=='request_restore')return;
    // Intent only: never write or claim success. A separate guarded flow
    // must obtain fresh server state and explicit confirmation.
    if(typeof onDecision==='function')onDecision({kind:item.kind,key:item.key,
      choice:'request_restore',requiresFreshRead:true});
    select.value='keep_deleted';
   });
   choices.push(select);block.appendChild(select);section.appendChild(block);
  }
  if(review.items.length)container.appendChild(section);
  return {rendered:review.items.length>0,dispose:()=>section.remove(),
   disable:()=>{for(const select of choices)select.disabled=true;}};
 }
 return {mount};
});
