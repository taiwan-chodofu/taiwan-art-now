const test=require('node:test'),assert=require('node:assert/strict');
const {mount}=require('../static/js/draft_server_button_bridge.js');
const response=(s,status=200)=>({ok:status===200,status,headers:{get:k=>k==='content-type'?'application/json':'no-store'},json:async()=>s});
function element(){const events=new Map(),attrs={};return {disabled:false,addEventListener:(n,f)=>events.set(n,f),removeEventListener:n=>events.delete(n),hasAttribute:()=>false,setAttribute:(k,v)=>attrs[k]=v,click:()=>events.get('click')?.(),get attrs(){return attrs;}};}
function fixture(){let state={revision:0,favs:{},visited:{}},posts=0;const fetchImpl=async(_,opts)=>{if(opts.method==='GET')return response(state);posts++;const data=JSON.parse(opts.body);const kind=Object.keys(data.changes).find(k=>Object.keys(data.changes[k]).length);const key=Object.keys(data.changes[kind])[0],op=data.changes[kind][key];state={...state,revision:1,[kind]:{...state[kind],[key]:{revision:1,deleted:!!op.delete,value:op.set}}};return response(state);};return {fetchImpl,get posts(){return posts;}};}
test('staging detail button verifies server then updates UI and disables stale action',async()=>{
 const f=fixture(),button=element(),notice=element(),win=element(),renders=[];
 const mounted=mount({win,fetchImpl:f.fetchImpl,buttons:[{element:button,kind:'favs',key:'art',action:'set',value:{title:'Art'},expectedRevision:0}],notice,lang:'ja',onRender:x=>renders.push(x)});
 await button.click();assert.equal(f.posts,1);assert.equal(renders.length,1);assert.equal(button.disabled,true);assert.match(notice.textContent,/サーバーに保存/);mounted.dispose();
});
test('uncertain POST never reports saved and tells user next action',async()=>{
 const button=element(),notice=element(),win=element(),renders=[];let posts=0;
 const fetchImpl=async(_,opts)=>{if(opts.method==='GET')return response({revision:0,favs:{},visited:{}});posts++;throw Error('offline');};
 mount({win,fetchImpl,buttons:[{element:button,kind:'visited',key:'art',action:'set',value:'today',expectedRevision:0}],notice,lang:'ja',onRender:x=>renders.push(x)});
 await button.click();assert.equal(posts,1);assert.equal(renders.length,0);assert.match(notice.textContent,/ページを再読み込み/);assert.doesNotMatch(notice.textContent,/サーバーに保存/);
});
test('inline legacy onclick is rejected to prevent double write',()=>{
 const button=element();button.onclick=()=>{};
 assert.throws(()=>mount({win:element(),fetchImpl:async()=>{},buttons:[{element:button,kind:'favs',key:'a',action:'set',value:true,expectedRevision:0}],notice:element()}),/invalid staging mount/);
});
