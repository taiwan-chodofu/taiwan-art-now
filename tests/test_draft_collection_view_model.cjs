const test=require("node:test");
const assert=require("node:assert/strict");
const {build}=require("../static/js/draft_collection_view_model.js");
const exhibitions=[{key:"a"},{key:"b"},{key:"c"},{key:"d"}];
const keyOf=item=>item.key;
test("Discover and My Page show consistent independent bookmark views",()=>{
 const bookmarks={favs:{a:true,b:true},visited:{b:true,c:true}};
 const before=JSON.stringify(bookmarks);
 const result=build({exhibitions,bookmarks,keyOf});
 assert.equal(result.status,"ready");
 assert.deepEqual(result.views.watchlist.items,[exhibitions[0]]);
 assert.deepEqual(result.views.seen.items,[exhibitions[1],exhibitions[2]]);
 assert.deepEqual(result.views.discoverUnbookmarked.items,[exhibitions[3]]);
 assert.equal(result.views.all.count,4);
 assert.equal(JSON.stringify(bookmarks),before);
});
test("removing Seen reveals earlier Want without recreating Want",()=>{
 const bookmarks={favs:{a:true},visited:{a:true}};
 assert.equal(build({exhibitions,bookmarks,keyOf}).views.watchlist.count,0);
 delete bookmarks.visited.a;
 assert.deepEqual(build({exhibitions,bookmarks,keyOf}).views.watchlist.items,[exhibitions[0]]);
});
test("Seen-only exhibition does not require Want history",()=>{
 const result=build({exhibitions,bookmarks:{favs:{},visited:{c:true}},keyOf});
 assert.deepEqual(result.views.seen.items,[exhibitions[2]]);
});
test("invalid inputs fail closed",()=>{
 assert.equal(build({exhibitions:null,bookmarks:{},keyOf}).status,"invalid_request");
});
