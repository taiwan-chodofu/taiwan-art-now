const test=require("node:test"),assert=require("node:assert/strict");
const {plan}=require("../static/js/draft_server_recovery.js");
const {verify}=require("../static/js/draft_recovery_verifier.js");
const fav={title:"台南展",museum:"Museum"};
function storage(){const data={taiwan_art_favs:"{}",taiwan_art_visited:"{}"};return {data,getItem:k=>data[k]??null};}
function server(){return {revision:2,favs:{a:{deleted:false,revision:1,value:fav}},visited:{v:{deleted:true,revision:2,value:null}}};}
function setup(){const st=storage(),sv=server(),p=plan({storage:st,serverState:sv});return {st,sv,p};}
test("no consent means no recovery action",()=>{
 const {st,sv,p}=setup(),r=verify({storage:st,serverState:sv,expectedRevision:2,reviewedCandidates:p.candidates,decisions:[{kind:"favs",key:"a",choice:"decide_later"}]});
 assert.equal(r.status,"nothing_selected");assert.deepEqual(r.accepted,[]);
});
test("explicit choice creates only a non-executable proposal",()=>{
 const {st,sv,p}=setup(),r=verify({storage:st,serverState:sv,expectedRevision:2,reviewedCandidates:p.candidates,decisions:[{kind:"favs",key:"a",choice:"restore"}]});
 assert.equal(r.status,"ready_for_explicit_restore");
 assert.equal(r.requiresFreshLocalLock,true);assert.equal(r.requiresExplicitWriteConfirmation,true);
 assert.equal(st.data.taiwan_art_favs,"{}");
});
test("fresh server revision mismatch fails closed",()=>{
 const {st,sv,p}=setup();sv.revision=3;
 assert.equal(verify({storage:st,serverState:sv,expectedRevision:2,reviewedCandidates:p.candidates,decisions:[{kind:"favs",key:"a",choice:"restore"}]}).status,"stale_server");
});
test("already restored locally is stale, never overwrite",()=>{
 const {st,sv,p}=setup();st.data.taiwan_art_favs=JSON.stringify({a:{title:"Local",museum:"M"}});
 assert.equal(verify({storage:st,serverState:sv,expectedRevision:2,reviewedCandidates:p.candidates,decisions:[{kind:"favs",key:"a",choice:"restore"}]}).status,"stale_review");
});
test("changed server item revision fails closed",()=>{
 const {st,sv,p}=setup();sv.favs.a.revision=2;
 assert.equal(verify({storage:st,serverState:sv,expectedRevision:2,reviewedCandidates:p.candidates,decisions:[{kind:"favs",key:"a",choice:"restore"}]}).status,"stale_review");
});
test("changed server value fails closed",()=>{
 const {st,sv,p}=setup();sv.favs.a.value={title:"Changed",museum:"M"};
 assert.equal(verify({storage:st,serverState:sv,expectedRevision:2,reviewedCandidates:p.candidates,decisions:[{kind:"favs",key:"a",choice:"restore"}]}).status,"stale_review");
});
test("tombstone is not a valid restore selection",()=>{
 const {st,sv,p}=setup();
 assert.equal(verify({storage:st,serverState:sv,expectedRevision:2,reviewedCandidates:p.candidates,decisions:[{kind:"visited",key:"v",choice:"restore"}]}).status,"invalid_request");
});
test("duplicate choices rejected",()=>{
 const {st,sv,p}=setup(),d={kind:"favs",key:"a",choice:"restore"};
 assert.equal(verify({storage:st,serverState:sv,expectedRevision:2,reviewedCandidates:p.candidates,decisions:[d,d]}).status,"invalid_request");
});
