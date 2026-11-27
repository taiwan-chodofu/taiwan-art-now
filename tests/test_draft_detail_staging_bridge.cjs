const test=require('node:test'),assert=require('node:assert/strict');
const {mount}=require('../static/js/draft_detail_staging_bridge.js');
function fixture(){
 const data={taiwan_art_favs:'{}',taiwan_art_visited:'{}'},events=[];
 const storage={getItem:k=>data[k]??null,setItem:(k,v)=>{data[k]=v;}};
 const listeners=new Map();
 const win={addEventListener:(k,fn)=>listeners.set(k,fn),removeEventListener:k=>listeners.delete(k)};
 function button(){const handlers=new Map();return {disabled:false,attrs:{},addEventListener:(k,fn)=>handlers.set(k,fn),removeEventListener:k=>handlers.delete(k),setAttribute(k,v){this.attrs[k]=v;},click(){if(!this.disabled)handlers.get('click')?.();},handlers};}
 const fav=button(),seen=button(),errorElement={hidden:true,textContent:''};
 const args={win,storage,locks:{request:(_k,_o,fn)=>Promise.resolve().then(fn)},key:'ex_1',metadata:{title:'展覽',museum:'M'},lang:'zh',buttons:[{kind:'favs',element:fav},{kind:'visited',element:seen}],errorElement,render:()=>events.push('render'),analytics:()=>events.push('analytics'),notify:()=>events.push('notify')};
 return {args,data,events,fav,seen,errorElement,listeners};
}
test('bridge rejects invalid controls before installing any listeners',()=>{
 const x=fixture();x.args.buttons=[{kind:'favs',element:x.fav},{kind:'favs',element:x.seen}];
 assert.throws(()=>mount(x.args),/invalid staging mount/);
 assert.equal(x.fav.handlers.size,0);assert.equal(x.listeners.size,0);
});
test('bridge commits independently and disposes on pagehide',async()=>{
 const x=fixture();mount(x.args);
 x.fav.click();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(x.fav.disabled,false);assert.equal(x.fav.attrs['aria-busy'],'false');
 assert.ok(JSON.parse(x.data.taiwan_art_favs).ex_1);
 assert.deepEqual(x.events,['render','analytics','notify']);
 x.listeners.get('pagehide')();
 assert.equal(x.fav.handlers.size,0);x.seen.click();await new Promise(resolve=>setImmediate(resolve));
 assert.deepEqual(JSON.parse(x.data.taiwan_art_visited),{});
});
test('bridge displays localized failure without analytics or notification',async()=>{
 const x=fixture();x.args.storage.setItem=()=>{throw Error('quota');};mount(x.args);
 x.fav.click();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(x.errorElement.hidden,false);
 assert.match(x.errorElement.textContent,/請確認裝置儲存空間/);
 assert.deepEqual(x.events,[]);
});

test('legacy inline click handler is rejected before bridge attaches',()=>{
 const x=fixture();x.fav.hasAttribute=name=>name==='onclick';
 assert.throws(()=>mount(x.args),/invalid staging mount/);
 assert.equal(x.fav.handlers.size,0);assert.equal(x.listeners.size,0);
});
