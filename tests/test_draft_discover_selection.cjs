const test=require("node:test");
const assert=require("node:assert/strict");
const {select}=require("../static/js/draft_discover_selection.js");
const cards=[{stable_key:"want"},{stable_key:"seen"},{stable_key:"both"},{stable_key:"new"}];
const bookmarks={favs:{want:true,both:true},visited:{seen:true,both:true}};
const normalizeKey=x=>x;
test("Discover default keeps wanted and new, hides Seen regardless of Want",()=>{
 const before=JSON.stringify(bookmarks);
 const result=select({cards,bookmarks,normalizeKey});
 assert.equal(result.status,"ready");
 assert.deepEqual(result.cards,[cards[0],cards[3]]);
 assert.equal(JSON.stringify(bookmarks),before);
});
test("unbookmarked Discover contains only exhibitions with neither bookmark",()=>{
 assert.deepEqual(select({cards,bookmarks,normalizeKey,mode:"unbookmarked"}).cards,[cards[3]]);
});
test("watchlist excludes Seen while Seen includes direct and prior Want",()=>{
 assert.deepEqual(select({cards,bookmarks,normalizeKey,mode:"watchlist"}).cards,[cards[0]]);
 assert.deepEqual(select({cards,bookmarks,normalizeKey,mode:"seen"}).cards,[cards[1],cards[2]]);
});
test("removing Seen reveals prior Want without changing Want",()=>{
 const next={favs:{both:true},visited:{}};
 assert.deepEqual(select({cards,bookmarks:next,normalizeKey,mode:"watchlist"}).cards,[cards[2]]);
});
test("invalid mode fails closed",()=>{
 assert.equal(select({cards,bookmarks,normalizeKey,mode:"other"}).status,"invalid_mode");
});
