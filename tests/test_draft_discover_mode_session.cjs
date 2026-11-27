const test=require("node:test");
const assert=require("node:assert/strict");
const {create}=require("../static/js/draft_discover_mode_session.js");
const cards=[{stable_key:"a"},{stable_key:"b"},{stable_key:"c"}];
const bookmarks={favs:{a:true},visited:{b:true}};
test("mode changes retain original order and never change bookmarks",()=>{
 const before=JSON.stringify(bookmarks);
 const session=create({cards,bookmarks,normalizeKey:x=>x});
 assert.deepEqual(session.visible().cards,[cards[0],cards[2]]);
 assert.deepEqual(session.change("unbookmarked").cards,[cards[2]]);
 assert.deepEqual(session.change("browse").cards,[cards[0],cards[2]]);
 assert.equal(JSON.stringify(bookmarks),before);
});
test("busy swipes prevent filter switching",()=>{
 const session=create({cards,bookmarks,normalizeKey:x=>x,canChange:()=>false});
 assert.equal(session.change("unbookmarked").status,"busy");
 assert.equal(session.getMode(),"browse");
});
test("mode change callback allows caller to clear stale undo history",()=>{
 let clears=0;
 const session=create({cards,bookmarks,normalizeKey:x=>x,onModeChanged:()=>clears++});
 session.change("unbookmarked");
 session.change("unbookmarked");
 assert.equal(clears,1);
});
test("updates reflect bookmark changes without rewriting saved state",()=>{
 const session=create({cards,bookmarks,normalizeKey:x=>x});
 const next={favs:{a:true},visited:{a:true,b:true}};
 assert.deepEqual(session.update({bookmarks:next}).cards,[cards[2]]);
 assert.equal(next.favs.a,true);
});
