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
   const keep=doc.createElement('button');
   keep.type='button';keep.textContent=item.options[0].label;
   keep.addEventListener('click',()=>{block.remove();});
   const restore=doc.createElement('button');
   restore.type='button';restore.textContent=item.options[1].label;
   restore.addEventListener('click',()=>{
    if(restore.disabled)return;
    restore.disabled=true;keep.disabled=true;
    // This only records intent. The authenticated confirmation flow
    // must be completed separately; do not claim restoration here.
    if(typeof onDecision==='function')onDecision({kind:item.kind,key:item.key,
      choice:'request_restore',requiresFreshRead:true});
   });
   choices.push(keep,restore);block.appendChild(keep);block.appendChild(restore);
   section.appendChild(block);

  }
  if(review.items.length)container.appendChild(section);
  return {rendered:review.items.length>0,dispose:()=>section.remove(),
   disable:()=>{for(const select of choices)select.disabled=true;}};
 }
 return {mount};
});
