const test=require("node:test");
const assert=require("node:assert/strict");
const {classify}=require("../static/js/draft_legacy_candidate_policy.js");
const state=(favs={},visited={})=>({revision:3,favs,visited});
const fav=(title)=>({title,museum:"Gallery"});
const active=(value,revision=2)=>({deleted:false,value,revision});
const tomb=(revision=2)=>({deleted:true,value:null,revision});
test("legacy absence never creates deletion",()=>{
 const r=classify({legacy:{favs:{},visited:{}},server:state({a:active(fav("A"))})});
 assert.deepEqual(r.adds,[]);assert.deepEqual(r.reviews,[]);
});
test("old tab cannot resurrect server tombstone",()=>{
 const r=classify({legacy:{favs:{a:fav("Old")},visited:{}},server:state({a:tomb()})});
 assert.equal(r.adds.length,0);assert.deepEqual(r.reviews,[{kind:"favs",key:"a",reason:"server_tombstone"}]);
});
test("legacy-only entries remain candidates, never committed",()=>{
 const r=classify({legacy:{favs:{a:fav("A")},visited:{b:"2026-11-23T00:00:00Z"}},server:state()});
 assert.equal(r.adds.length,2);assert.equal(r.requiresServerCAS,true);
});
test("server metadata is never overwritten",()=>{
 const r=classify({legacy:{favs:{a:fav("Stale")},visited:{}},server:state({a:active(fav("Fresh"))})});
 assert.equal(r.adds.length,0);assert.equal(r.reviews.length,0);
});
test("malformed server revision fails closed",()=>{
 assert.equal(classify({legacy:{favs:{},visited:{}},server:{revision:-1,favs:{},visited:{}}}).status,"invalid_input");
});
test("invalid legacy item and malformed tombstone fail closed",()=>{
 assert.equal(classify({legacy:{favs:{a:{title:"Missing museum"}},visited:{}},server:state()}).status,"invalid_input");
 assert.equal(classify({legacy:{favs:{a:fav("A")},visited:{}},server:state({a:{deleted:true,value:fav("A"),revision:2}})}).status,"invalid_input");
});
test("zero revision empty server is valid",()=>{
 assert.equal(classify({legacy:{favs:{},visited:{}},server:{revision:0,favs:{},visited:{}}}).status,"classified");
});
