const assert=require('node:assert/strict');
const {test}=require('node:test');
const {restore}=require('../static/js/draft_explicit_server_restore.js');
function state(revision,deleted=true){return {revision,favs:{art:{revision:1,deleted,value:deleted?null:true}},visited:{}};}
function response(body,status=200){return {status,ok:status>=200&&status<300,headers:{get:k=>k==='content-type'?'application/json':k==='cache-control'?'no-store':null},json:async()=>body};}
test('explicit confirmation and reviewed tombstone required',async()=>{
 let calls=0;const fetchImpl=async()=>{calls++;return response(state(1));};
 assert.equal((await restore({fetchImpl,kind:'favs',key:'art',value:true,reviewedRevision:1,tombstoneRevision:1})).status,'not_authorized');
 assert.equal(calls,0);
});
test('confirmed tombstone restored only after fresh GET, CAS and verification',async()=>{
 let server=state(1),posts=0;
 const fetchImpl=async(_url,options)=>{
  if(options.method==='GET')return response(server);
  posts++;const payload=JSON.parse(options.body);
  assert.equal(payload.base_revision,1);
  assert.deepEqual(payload.changes.favs.art,{set:true});
  server={revision:2,favs:{art:{revision:2,deleted:false,value:true}},visited:{}};
  return response(server);
 };
 const result=await restore({fetchImpl,kind:'favs',key:'art',value:true,reviewedRevision:1,tombstoneRevision:1,confirmed:true});
 assert.equal(result.status,'server_confirmed');assert.equal(posts,1);
});
test('changed revision rejects restore before POST',async()=>{
 let posts=0;
 const fetchImpl=async(_url,options)=>{if(options.method==='POST')posts++;return response(state(2));};
 const result=await restore({fetchImpl,kind:'favs',key:'art',value:true,reviewedRevision:1,tombstoneRevision:1,confirmed:true});
 assert.equal(result.status,'review_expired');assert.equal(posts,0);
});
test('uncertain POST never retries',async()=>{
 let posts=0;
 const fetchImpl=async(_url,options)=>{if(options.method==='POST'){posts++;throw Error('network');}return response(state(1));};
 const result=await restore({fetchImpl,kind:'favs',key:'art',value:true,reviewedRevision:1,tombstoneRevision:1,confirmed:true});
 assert.equal(result.status,'write_outcome_unknown');assert.equal(posts,1);
});
