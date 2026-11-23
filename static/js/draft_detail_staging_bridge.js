/* DRAFT ONLY. Opt-in staging bridge; never loaded by production templates. */
(function(root,factory){
 const api=factory(typeof module==='object'&&module.exports?require('./draft_detail_action_adapter.js'):root.TanDraftDetailActionAdapter,
   typeof module==='object'&&module.exports?require('./draft_detail_failure_copy.js'):root.TanDraftDetailFailureCopy);
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.TanDraftDetailStagingBridge=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(adapterApi,copy){
 'use strict';
 function mount({win,storage,locks,key,metadata,lang='zh',render,analytics,notify,warn,buttons,errorElement}={}){
  if(!win||!storage||typeof key!=='string'||!key||!Array.isArray(buttons)||buttons.length!==2||!errorElement||!buttons.every(b=>b&&['favs','visited'].includes(b.kind)&&b.element)||new Set(buttons.map(b=>b.kind)).size!==2)throw Error('invalid staging mount');
  let disposed=false;
  const setBusy=({kind,busy})=>{const button=buttons.find(b=>b.kind===kind)?.element;if(button){button.disabled=busy;button.setAttribute('aria-busy',String(busy));}};
  const instance=adapterApi.create({storage,locks,key,metadata,
   onBusy:setBusy,
   onRender:detail=>{errorElement.hidden=true;if(typeof render==='function')render(detail);},
   onAnalytics:detail=>{if(typeof analytics==='function')analytics(detail);},
   onNotify:detail=>{if(typeof notify==='function')notify(detail);if(typeof warn==='function')warn(detail);},
   onFailure:({status})=>{errorElement.textContent=copy.message(status,lang);errorElement.hidden=false;}
  });
  const handlers=[];
  for(const {kind,element} of buttons){
   const fn=()=>{void instance.toggle(kind);};element.addEventListener('click',fn);handlers.push([element,fn]);}
  const dispose=()=>{if(disposed)return;disposed=true;instance.dispose();for(const [el,fn] of handlers)el.removeEventListener('click',fn);win.removeEventListener('pagehide',dispose);};
  win.addEventListener('pagehide',dispose,{once:true});
  return {dispose,isBusy:instance.isBusy};
 }
 return {mount};
});
