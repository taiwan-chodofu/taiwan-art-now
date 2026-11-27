const test=require("node:test");
const assert=require("node:assert/strict");
const {check}=require("../static/js/draft_review_status_check.js");
const value={title:"A",museum:"M"};
const state=(entry)=>({revision:7,favs:entry?{a:entry}:{},visited:{}});
const response=body=>({ok:true,status:200,headers:{get:k=>k==="content-type"?"application/json":"no-store"},json:async()=>body});
const fetchState=body=>async(path,opts)=>{
 assert.equal(path,"/api/private-subscribers/v2/state");
 assert.equal(opts.method,"GET");
 assert.equal(opts.credentials,"same-origin");
 return response(body);
};
test("read-only check confirms matching server registration",async()=>{
 const result=await check({kind:"favs",key:"a",expectedValue:value,
   fetchImpl:fetchState(state({value:{museum:"M",title:"A"},revision:7,deleted:false}))});
 assert.equal(result.status,"saved_on_server");
});
test("server tombstone remains unresolved and never causes a write",async()=>{
 let calls=0;
 const result=await check({kind:"favs",key:"a",expectedValue:value,
   fetchImpl:async(path,opts)=>{calls++;assert.equal(opts.method,"GET");
     return response(state({value:null,revision:7,deleted:true}));}});
 assert.equal(result.status,"still_deleted");
 assert.equal(calls,1);
});
test("different active value is not misreported as saved",async()=>{
 const result=await check({kind:"favs",key:"a",expectedValue:value,
   fetchImpl:fetchState(state({value:{title:"Other",museum:"M"},revision:7,deleted:false}))});
 assert.equal(result.status,"different_server_value");
});
test("missing entry is not proof of a successful save",async()=>{
 const result=await check({kind:"favs",key:"a",expectedValue:value,
   fetchImpl:fetchState(state())});
 assert.equal(result.status,"not_found");
});
test("network failure is unverified and never retries",async()=>{
 let calls=0;
 const result=await check({kind:"favs",key:"a",expectedValue:value,
   fetchImpl:async()=>{calls++;throw Error("offline");}});
 assert.equal(result.status,"unverified");
 assert.equal(calls,1);
});
test("invalid request makes no network call",async()=>{
 const result=await check({kind:"favs",key:"",expectedValue:value,
   fetchImpl:async()=>{throw Error("must not fetch");}});
 assert.equal(result.status,"invalid_request");
});
