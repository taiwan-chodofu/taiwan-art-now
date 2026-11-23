const test=require('node:test');
const assert=require('node:assert/strict');
const review=require('../static/js/draft_migration_review.js');
function storage(favs,visited){
 const maps={'taiwan_art_favs':JSON.stringify(favs),'taiwan_art_visited':JSON.stringify(visited)};
 return {getItem(key){return Object.hasOwn(maps,key)?maps[key]:null;}};
}
test('migration review explains local-only, remote-only and explicit deletion without writes',()=>{
 const local=storage({local:{title:'Local'},deleted:{title:'Old'}},{});
 const server={revision:3,favs:{
  remote:{revision:1,deleted:false,value:{title:'Remote'}},
  deleted:{revision:2,deleted:true,value:null}
 },visited:{seen:{revision:3,deleted:false,value:{title:'Seen'}}}};
 const report=review.preview(local,server);
 assert.equal(report.status,'ready');
 const ja=review.explain(report,'ja');
 assert.equal(ja.status,'ready');assert.equal(ja.mayWrite,false);
 assert.match(ja.items.find(x=>x.key==='local').message,/この端末だけ/);
 assert.match(ja.items.find(x=>x.key==='remote').message,/削除しません/);
 assert.match(ja.items.find(x=>x.key==='deleted').message,/自動復元はしません/);
 assert.match(ja.items.find(x=>x.key==='seen').message,/削除しません/);
 const zh=review.explain(report,'zh');
 assert.equal(zh.mayWrite,false);
 assert.match(zh.items.find(x=>x.key==='deleted').message,/不會自動恢復/);
 assert.match(zh.items.find(x=>x.key==='remote').message,/不代表刪除/);
});
test('migration review cannot turn invalid report into permission to write',()=>{
 assert.deepEqual(review.explain(null),{status:'invalid_review',mayWrite:false,items:[]});
 assert.deepEqual(review.explain({status:'ready',rows:null}),{status:'invalid_review',mayWrite:false,items:[]});
});
