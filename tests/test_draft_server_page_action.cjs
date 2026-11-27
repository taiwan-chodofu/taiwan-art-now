const test=require('node:test'),assert=require('node:assert/strict');
const {create}=require('../static/js/draft_server_page_action.js');
const response=(state,status=200)=>({ok:status===200,status,headers:{get:k=>k==='content-type'?'application/json':'no-store'},json:async()=>state});
function harness(){let state={revision:0,favs:{},visited:{}},writes=0;const fetchImpl=async(_path,options)=>{
 if(options.method==='GET')return response(state);
 writes++;const {base_revision,changes}=JSON.parse(options.body);
 if(base_revision!==state.revision)return response({},409);
 const revision=++state.revision;
 for(const kind of ['favs','visited'])for(const [key,op] of Object.entries(changes[kind]))
  state[kind][key]={revision,deleted:!!op.delete,value:op.delete?null:op.set};
 return response(state);
};return {fetchImpl,get writes(){return writes;},get state(){return state;}};}
test('detail and Discover share server-first action with independent flags',async()=>{
 const h=harness(),renders=[],analytics=[];
 const action=create({fetchImpl:h.fetchImpl,onRender:x=>renders.push(x),onAnalytics:x=>analytics.push(x)});
 assert.equal((await action.act({kind:'favs',key:'art',action:'set',value:{title:'Art'},expectedRevision:0})).status,'server_confirmed');
 assert.equal((await action.act({kind:'visited',key:'art',action:'set',value:'2026-11-23',expectedRevision:1})).status,'server_confirmed');
 assert.equal(h.writes,2);assert.equal(renders.length,2);assert.equal(analytics.length,2);
 assert.equal(h.state.favs.art.deleted,false);assert.equal(h.state.visited.art.deleted,false);
});
test('stale revision never triggers success callbacks',async()=>{
 const h=harness(),renders=[],failures=[];
 const action=create({fetchImpl:h.fetchImpl,onRender:x=>renders.push(x),onFailure:x=>failures.push(x)});
 await action.act({kind:'favs',key:'art',action:'set',value:true,expectedRevision:0});
 const result=await action.act({kind:'visited',key:'art',action:'set',value:true,expectedRevision:0});
 assert.equal(result.status,'stale_revision');assert.equal(h.writes,1);
 assert.equal(renders.length,1);assert.equal(failures[0].status,'stale_revision');
});
test('no automatic retry or success on uncertain write',async()=>{
 const h=harness(),renders=[],failures=[];let posts=0;
 const fetchImpl=async(path,options)=>{if(options.method==='POST'){posts++;throw Error('network');}return h.fetchImpl(path,options);};
 const action=create({fetchImpl,onRender:x=>renders.push(x),onFailure:x=>failures.push(x)});
 const result=await action.act({kind:'favs',key:'a',action:'set',value:true,expectedRevision:0});
 assert.equal(result.status,'write_outcome_unknown');assert.equal(posts,1);
 assert.equal(renders.length,0);assert.equal(failures.length,1);
});
test('disposed action never writes',async()=>{
 const h=harness(),action=create({fetchImpl:h.fetchImpl});action.dispose();
 assert.equal((await action.act({kind:'favs',key:'a',action:'set',value:true,expectedRevision:0})).status,'disposed');
 assert.equal(h.writes,0);
});
