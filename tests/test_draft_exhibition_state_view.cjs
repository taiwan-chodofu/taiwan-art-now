const test=require("node:test");
const assert=require("node:assert/strict");
const {describe,show}=require("../static/js/draft_exhibition_state_view.js");
test("saved state identifies both collections",()=>{
 assert.match(describe({status:"saved",collections:["favs","visited"]}).detail,/想看、看過/);
});
test("unavailable state never suggests saving again",()=>{
 const text=describe({status:"unconfirmed"}).detail;
 assert.match(text,/稍後再試/);
 assert.doesNotMatch(text,/再次收藏/);
});
test("removed state offers choice but never performs it",()=>{
 assert.match(describe({status:"removed"}).detail,/自行選擇/);
});
test("invalid rendering container does not fetch",async()=>{
 assert.equal((await show({})).status,"invalid_request");
});

test("partial removal explains both states in the same sentence",()=>{
 const message=describe({status:"saved",collections:["favs"],removedCollections:["visited"]});
 assert.match(message.detail,/已加入：想看/);
 assert.match(message.detail,/已從「看過」移除/);
});
