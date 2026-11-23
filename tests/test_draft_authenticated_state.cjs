const test=require("node:test"),assert=require("node:assert/strict");
const {read,PATH}=require("../static/js/draft_authenticated_state.js");
const state={revision:1,favs:{a:{deleted:false,revision:1,value:{title:"A",museum:"M"}}},visited:{}};
function response(status=200,body=state,ct="application/json",cc="no-store"){
 return {status,ok:status>=200&&status<300,
   headers:{get:k=>k==="content-type"?ct:k==="cache-control"?cc:null},
   json:async()=>body};
}
test("fetch uses only authenticated same-origin noncacheable GET",async()=>{
 let seen;const r=await read({fetchImpl:async(...args)=>{seen=args;return response();}});
 assert.equal(r.status,"ready");assert.deepEqual(r.state,state);
 assert.equal(seen[0],PATH);assert.equal(seen[1].credentials,"same-origin");
 assert.equal(seen[1].redirect,"error");assert.equal(seen[1].cache,"no-store");
 assert.equal(seen[1].mode,"same-origin");
});
test("unauthorized response never returns data",async()=>{
 assert.equal((await read({fetchImpl:async()=>response(403)})).status,"unauthorized");
});
test("redirected login page is rejected",async()=>{
 assert.equal((await read({fetchImpl:async()=>response(200,{},"text/html")})).status,"invalid_response");
});
test("cacheable response is rejected",async()=>{
 assert.equal((await read({fetchImpl:async()=>response(200,state,"application/json","public,max-age=60")})).status,"invalid_response");
});
test("invalid server shape fails closed",async()=>{
 assert.equal((await read({fetchImpl:async()=>response(200,{revision:-1,favs:{},visited:{}})})).status,"invalid_server");
});
test("offline never returns data",async()=>{
 assert.equal((await read({fetchImpl:async()=>{throw Error("offline");}})).status,"unavailable");
});
test("no fetch dependency fails closed",async()=>{
 assert.equal((await read({})).status,"invalid_request");
});
