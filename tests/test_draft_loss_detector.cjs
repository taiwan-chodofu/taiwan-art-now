const test = require("node:test");
const assert = require("node:assert/strict");
const {inspect} = require("../static/js/draft_loss_detector.js");
const fav = {title:"A",museum:"M"};
function storage(favs={},visited={}) {
  const data = {taiwan_art_favs:JSON.stringify(favs),taiwan_art_visited:JSON.stringify(visited)};
  return {getItem:k=>data[k]??null};
}
const checkpoint = {favs:{a:fav},visited:{v:"2026-11-23T01:02:03.000Z"}};
test("detects a saved favorite overwritten by cached legacy tab",()=>{
  const r=inspect({storage:storage({older:{title:"Old",museum:"M"}},{v:checkpoint.visited.v}),checkpoint});
  assert.equal(r.status,"needs_review");
  assert.deepEqual(r.missing,[{kind:"favs",key:"a",reason:"checkpoint_entry_missing"}]);
  assert.deepEqual(r.additions,[{kind:"favs",key:"older"}]);
});
test("missing legacy record never becomes an inferred deletion",()=>{
  const r=inspect({storage:storage(),checkpoint});
  assert.equal(r.missing.length,2);
  assert.equal(r.status,"needs_review");
  assert.equal("changes" in r,false);
});
test("metadata mismatch is review-only",()=>{
  const r=inspect({storage:storage({a:{title:"Different",museum:"M"}},{v:checkpoint.visited.v}),checkpoint});
  assert.equal(r.changed.length,1);
  assert.equal(r.missing.length,0);
});
test("additions alone are consistent and preserved",()=>{
  const r=inspect({storage:storage({a:fav,b:{title:"B",museum:"M"}},{v:checkpoint.visited.v}),checkpoint});
  assert.equal(r.status,"consistent");
  assert.deepEqual(r.additions,[{kind:"favs",key:"b"}]);
});
test("invalid checkpoint is rejected without touching storage",()=>{
  assert.equal(inspect({storage:{getItem(){throw Error("unexpected")}},checkpoint:{favs:{a:1},visited:{}}}).status,"invalid_checkpoint");
});
test("invalid local storage fails closed",()=>{
  assert.equal(inspect({storage:{getItem(){return "bad json";}},checkpoint}).status,"invalid_local");
});
