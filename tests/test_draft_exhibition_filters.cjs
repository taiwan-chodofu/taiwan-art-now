const test=require("node:test");
const assert=require("node:assert/strict");
const {classify,matches,filterExhibitions}=require("../static/js/draft_exhibition_filters.js");
test("want-only is on watchlist",()=>{
 assert.deepEqual(classify("a",{favs:{a:true},visited:{}}),
  {want:true,seen:false,watchlist:true,seenList:false,unbookmarked:false});
});
test("seen-only is valid without prior want bookmark",()=>{
 const state=classify("a",{favs:{},visited:{a:"2026-11-23"}});
 assert.equal(state.seenList,true);
 assert.equal(state.watchlist,false);
});
test("seen suppresses watchlist display without deleting want bookmark",()=>{
 const bookmarks={favs:{a:{title:"A"}},visited:{a:"2026-11-23"}};
 const before=JSON.stringify(bookmarks);
 assert.equal(matches("a",bookmarks,"watchlist"),false);
 assert.equal(matches("a",bookmarks,"seen"),true);
 assert.equal(JSON.stringify(bookmarks),before);
 delete bookmarks.visited.a;
 assert.equal(matches("a",bookmarks,"watchlist"),true);
});
test("unbookmarked discovery excludes either kind of bookmark",()=>{
 const bookmarks={favs:{a:true},visited:{b:true}};
 assert.equal(matches("a",bookmarks,"unbookmarked"),false);
 assert.equal(matches("b",bookmarks,"unbookmarked"),false);
 assert.equal(matches("c",bookmarks,"unbookmarked"),true);
});
test("versioned deletion is not counted as active bookmark",()=>{
 const bookmarks={favs:{a:{value:{title:"A"},deleted:true,revision:2}},visited:{}};
 assert.equal(matches("a",bookmarks,"unbookmarked"),true);
});
test("filters preserve source order and do not mutate entries",()=>{
 const exhibitions=[{id:"a"},{id:"b"},{id:"c"}];
 const bookmarks={favs:{a:true,b:true},visited:{b:true}};
 const result=filterExhibitions(exhibitions,bookmarks,"watchlist",x=>x.id);
 assert.deepEqual(result,{status:"ready",items:[exhibitions[0]]});
 assert.equal(exhibitions.length,3);
 assert.equal(bookmarks.favs.b,true);
});
test("invalid filter never silently returns all",()=>{
 assert.equal(filterExhibitions([{id:"a"}],{},"nonsense",x=>x.id).status,"invalid_filter");
});
