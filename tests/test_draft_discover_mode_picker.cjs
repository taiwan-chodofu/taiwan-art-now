const test=require("node:test");
const assert=require("node:assert/strict");
const {mount,labels}=require("../static/js/draft_discover_mode_picker.js");
test("Taiwanese explanation clearly says bookmarks are never deleted",()=>{
 assert.match(labels.zh.description,/不會刪除任何收藏/);
 assert.match(labels.zh.unbookmarked,/尚未收藏/);
});
test("Japanese and English explanations describe hiding, not deleting",()=>{
 assert.match(labels.ja.description,/削除されません/);
 assert.match(labels.en.description,/No bookmarks are removed/);
});
test("invalid mounting does not trigger callback",()=>{
 let calls=0;
 assert.equal(mount({onChange:()=>calls++}).status,"invalid_request");
 assert.equal(calls,0);
});
