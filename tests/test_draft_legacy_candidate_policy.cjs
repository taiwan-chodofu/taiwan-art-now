const test=require("node:test");
const assert=require("node:assert/strict");
const {classify}=require("../static/js/draft_legacy_candidate_policy.js");
const state=(favs={},visited={})=>({revision:3,favs,visited});
test("legacy absence never creates deletion",()=>{
 const r=classify({legacy:{favs:{},visited:{}},server:state({a:{deleted:false}})});
 assert.deepEqual(r.adds,[]);assert.deepEqual(r.reviews,[]);
});
test("old tab cannot resurrect server tombstone",()=>{
 const r=classify({legacy:{favs:{a:{title:"Old"}},visited:{}},server:state({a:{deleted:true,revision:2}})});
 assert.equal(r.adds.length,0);assert.deepEqual(r.reviews,[{kind:"favs",key:"a",reason:"server_tombstone"}]);
});
test("new legacy-only entries are additive candidates, not committed",()=>{
 const r=classify({legacy:{favs:{a:{title:"A"}},visited:{b:"2026-11-23T00:00:00Z"}},server:state()});
 assert.equal(r.adds.length,2);assert.equal(r.requiresServerCAS,true);
});
test("server metadata is never overwritten",()=>{
 const r=classify({legacy:{favs:{a:{title:"Stale"}},visited:{}},server:state({a:{deleted:false,title:"Fresh"}})});
 assert.equal(r.adds.length,0);assert.equal(r.reviews.length,0);
});
test("malformed server revision fails closed",()=>{
 assert.equal(classify({legacy:{favs:{},visited:{}},server:{revision:0,favs:{},visited:{}}}).status,"invalid_input");
});
