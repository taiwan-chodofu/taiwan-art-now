const test=require('node:test');
const assert=require('node:assert/strict');
const review=require('../static/js/draft_migration_review.js');
function storage(favs,visited){
 const maps={'taiwan_art_favs':JSON.stringify(favs),'taiwan_art_visited':JSON.stringify(visited)};
 return {getItem(key){return Object.hasOwn(maps,key)?maps[key]:null;}};
}
test('migration review explains local-only, remote-only and explicit deletion without writes',()=>{
 const local=storage({local:{title:'Local',museum:'M'},deleted:{title:'Old',museum:'M'}},{});
 const server={revision:3,favs:{
  remote:{revision:1,deleted:false,value:{title:'Remote'}},
  deleted:{revision:2,deleted:true,value:null}
 },visited:{seen:{revision:3,deleted:false,value:{title:'Seen'}}}};
 const report=review.preview(local,server);
 assert.equal(report.status,'ready');
 const ja=review.explain(report,'ja');
 assert.equal(ja.status,'ready');assert.equal(ja.mayWrite,false);
 assert.equal(ja.items.length,1);
 assert.equal(ja.items[0].key,'deleted');
 assert.match(ja.items[0].title,/戻しますか/);
 assert.match(ja.items[0].message,/以前/);
 assert.deepEqual(ja.items[0].options.map(x=>x.id),['keep_deleted','request_restore']);
 const zh=review.explain(report,'zh');
 assert.equal(zh.mayWrite,false);
 assert.equal(zh.items.length,1);
 assert.match(zh.items[0].title,/重新加入/);
 assert.equal(zh.items[0].options[0].label,'維持移除');
});
test('migration review cannot turn invalid report into permission to write',()=>{
 assert.deepEqual(review.explain(null),{status:'invalid_review',mayWrite:false,items:[]});
 assert.deepEqual(review.explain({status:'ready',rows:null}),{status:'invalid_review',mayWrite:false,items:[]});
});
