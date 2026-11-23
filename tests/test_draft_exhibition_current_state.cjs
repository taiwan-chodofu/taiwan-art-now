const test=require("node:test");
const assert=require("node:assert/strict");
const {check}=require("../static/js/draft_exhibition_current_state.js");
function fetchState(state){
 return async(url,opts)=>{
  assert.equal(url,"/api/private-subscribers/v2/state");
  assert.equal(opts.method,"GET");
  assert.equal(opts.credentials,"same-origin");
  return {ok:true,status:200,headers:{get:key=>key==="content-type"?"application/json":
   key==="cache-control"?"private, no-store":null},json:async()=>state};
 };
}
const base={revision:3,favs:{},visited:{}};
test("detail check reports both saved collections without any writes",async()=>{
 const state={...base,favs:{x:{value:1,deleted:false}},visited:{x:{value:1,deleted:false}}};
 const result=await check({fetchImpl:fetchState(state),exhibitionKey:"x"});
 assert.deepEqual(result,{status:"saved",revision:3,collections:["favs","visited"]});
});
test("detail check distinguishes explicit deletion from absence",async()=>{
 const deleted=await check({fetchImpl:fetchState({...base,favs:{x:{deleted:true}}}),exhibitionKey:"x"});
 assert.equal(deleted.status,"removed");
 const missing=await check({fetchImpl:fetchState(base),exhibitionKey:"x"});
 assert.equal(missing.status,"not_found");
});
test("detail check never treats network failure as unsaved",async()=>{
 const result=await check({fetchImpl:async()=>{throw Error("offline");},exhibitionKey:"x"});
 assert.equal(result.status,"unconfirmed");
});
test("detail check refuses missing identity",async()=>{
 assert.equal((await check({fetchImpl:fetchState(base),exhibitionKey:""})).status,"invalid_request");
});
