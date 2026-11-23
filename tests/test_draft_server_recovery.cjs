const test=require("node:test"),assert=require("node:assert/strict");
const {plan}=require("../static/js/draft_server_recovery.js");
function storage(favs={},visited={}){
 const d={taiwan_art_favs:JSON.stringify(favs),taiwan_art_visited:JSON.stringify(visited)};
 return {getItem:k=>d[k]??null};
}
const fav={title:"A",museum:"M"};
const state=()=>({revision:3,favs:{
 remote:{deleted:false,revision:1,value:fav},
 gone:{deleted:true,revision:2,value:null}
},visited:{v:{deleted:false,revision:3,value:"2026-11-23T01:02:03.000Z"}}});
test("remote-only active entries become consent-gated candidates, not writes",()=>{
 const s=storage(),r=plan({storage:s,serverState:state()});
 assert.equal(r.status,"prepared");assert.equal(r.candidates.length,2);
 assert.equal(r.requiresExplicitRestoreConsent,true);
 assert.equal("changes" in r,false);
 assert.deepEqual(r.candidates.map(x=>x.key),["remote","v"]);
});
test("remote tombstones never become restoration candidates",()=>{
 const r=plan({storage:storage(),serverState:state()});
 assert.equal(r.candidates.some(x=>x.key==="gone"),false);
});
test("local registration vs explicit tombstone needs review",()=>{
 const r=plan({storage:storage({gone:fav}),serverState:state()});
 assert.equal(r.status,"needs_review");
 assert.deepEqual(r.tombstoneConflicts,[{kind:"favs",key:"gone",reason:"explicit_deletion_conflict",item_revision:2}]);
});
test("local-only data is preserved, not deletion",()=>{
 const r=plan({storage:storage({local:fav}),serverState:state()});
 assert.deepEqual(r.localOnly,[{kind:"favs",key:"local"}]);
 assert.equal(r.candidates.some(x=>x.key==="local"),false);
});
test("metadata differences do not overwrite local or server",()=>{
 const r=plan({storage:storage({remote:{title:"Other",museum:"M"}}),serverState:state()});
 assert.deepEqual(r.metadataDifferences,[{kind:"favs",key:"remote",reason:"metadata_diff_preserved"}]);
});
test("invalid active remote payload fails closed",()=>{
 const s=state();s.favs.remote.value={title:12,museum:"M"};
 assert.equal(plan({storage:storage(),serverState:s}).status,"invalid_server_value");
});
test("invalid server revision fails closed",()=>{
 const s=state();s.revision=-1;
 assert.equal(plan({storage:storage(),serverState:s}).status,"invalid_server");
});
test("unreadable local storage never generates recovery proposals",()=>{
 const r=plan({storage:{getItem(){throw Error("blocked");}},serverState:state()});
 assert.equal(r.status,"unavailable");
});
