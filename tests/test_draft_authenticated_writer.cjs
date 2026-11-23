const test=require('node:test'),assert=require('node:assert/strict');
const {commit}=require('../static/js/draft_authenticated_writer.js');
const response=(state,status=200)=>({ok:status===200,status,headers:{get:k=>k==='content-type'?'application/json':'no-store'},json:async()=>state});
function fixture(){
 let state={revision:0,favs:{},visited:{}},posts=0;
 const fetchImpl=async(path,opts)=>{
  if(opts.method==='GET')return response(state);
  posts++;
  const {base_revision,changes}=JSON.parse(opts.body);
  if(base_revision!==state.revision)return response({},409);
  const next=state.revision+1;
  state={...state,revision:next,favs:{...state.favs},visited:{...state.visited}};
  for(const kind of ['favs','visited'])for(const [key,op] of Object.entries(changes[kind]))
   state[kind][key]={revision:next,deleted:!!op.delete,value:op.delete?null:op.set};
  return response(state);
 };
 return {fetchImpl,get posts(){return posts;},get state(){return state;},set state(v){state=v;}};
}
test('server-confirmed want and seen stay independent without localStorage writes',async()=>{
 const f=fixture();
 assert.equal((await commit({fetchImpl:f.fetchImpl,kind:'favs',key:'a',action:'set',value:{title:'A'},expectedRevision:0})).status,'server_confirmed');
 assert.equal((await commit({fetchImpl:f.fetchImpl,kind:'visited',key:'a',action:'set',value:'2026-11-23',expectedRevision:1})).status,'server_confirmed');
 assert.equal(f.posts,2);assert.equal(f.state.favs.a.deleted,false);assert.equal(f.state.visited.a.deleted,false);
});
test('stale revision does not POST',async()=>{
 const f=fixture();f.state={revision:1,favs:{},visited:{}};
 assert.equal((await commit({fetchImpl:f.fetchImpl,kind:'favs',key:'a',action:'set',value:true,expectedRevision:0})).status,'stale_revision');assert.equal(f.posts,0);
});
test('tombstone requires review, never silent resurrection',async()=>{
 const f=fixture();f.state={revision:2,favs:{a:{revision:2,deleted:true,value:null}},visited:{}};
 assert.equal((await commit({fetchImpl:f.fetchImpl,kind:'favs',key:'a',action:'set',value:true,expectedRevision:2})).status,'deletion_review_required');assert.equal(f.posts,0);
});
test('network loss after POST yields uncertain outcome and never retries',async()=>{
 let posts=0;const f=fixture();const fetchImpl=async(path,opts)=>{
  if(opts.method==='POST'){posts++;throw Error('lost response');}
  return f.fetchImpl(path,opts);
 };
 const r=await commit({fetchImpl,kind:'favs',key:'a',action:'set',value:true,expectedRevision:0});
 assert.equal(r.status,'write_outcome_unknown');assert.equal(r.committed,false);assert.equal(posts,1);
});
test('readback mismatch never reports success',async()=>{
 const f=fixture();let reads=0;
 const fetchImpl=async(path,opts)=>{
  if(opts.method==='GET'){reads++;if(reads===2)return response({revision:1,favs:{},visited:{}});}
  return f.fetchImpl(path,opts);
 };
 const r=await commit({fetchImpl,kind:'favs',key:'a',action:'set',value:true,expectedRevision:0});
 assert.equal(r.status,'write_outcome_unknown');assert.equal(r.committed,false);
});
