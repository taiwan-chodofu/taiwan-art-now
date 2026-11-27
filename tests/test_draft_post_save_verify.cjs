const test=require("node:test");
const assert=require("node:assert/strict");
const {verify}=require("../static/js/draft_post_save_verify.js");
const fav={title:"Art",museum:"Museum"};
const changes={favs:{art:{set:fav}},visited:{}};
function response(body,status=200){
 return {status,ok:status>=200&&status<300,
  headers:{get:k=>k==="content-type"?"application/json":k==="cache-control"?"no-store":null},
  json:async()=>body};
}
const state=(revision,entry)=>({revision,favs:entry?{art:entry}:{},visited:{}});
test("read-only check confirms previously committed record without POST",async()=>{
 let gets=0;
 const result=await verify({committedRevision:2,changes,fetchImpl:async(path,options)=>{
  assert.equal(options.method,"GET");gets++;
  return response(state(3,{value:fav,deleted:false,revision:2}));
 }});
 assert.equal(result.status,"confirmed_on_server");
 assert.equal(result.verifiedCount,1);
 assert.equal(gets,1);
});
test("later explicit server deletion is not silently restored",async()=>{
 const result=await verify({committedRevision:2,changes,fetchImpl:async()=>response(
  state(3,{value:null,deleted:true,revision:3}))});
 assert.equal(result.status,"server_records_need_review");
 assert.equal(result.unresolved[0].reason,"deleted_on_server");
});
test("missing server record is not reported as confirmed",async()=>{
 const result=await verify({committedRevision:2,changes,
  fetchImpl:async()=>response(state(2))});
 assert.equal(result.status,"server_records_need_review");
});
test("stale or inaccessible server check does not override earlier success",async()=>{
 const stale=await verify({committedRevision:3,changes,
  fetchImpl:async()=>response(state(2,{value:fav,deleted:false,revision:2}))});
 assert.equal(stale.status,"could_not_verify");
 assert.equal(stale.reason,"older_revision");
 const offline=await verify({committedRevision:3,changes,
  fetchImpl:async()=>{throw Error("offline");}});
 assert.equal(offline.status,"could_not_verify");
});
test("invalid request never fetches",async()=>{
 let calls=0;
 const result=await verify({committedRevision:2,changes:{favs:{},visited:{}},
  fetchImpl:async()=>{calls++;return response(state(2));}});
 assert.equal(result.status,"invalid_request");
 assert.equal(calls,0);
});
