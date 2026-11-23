const test=require('node:test'),assert=require('node:assert/strict');
const {inspect}=require('../static/js/draft_authenticated_recovery_review.js');
const value={title:'A',museum:'M'};
const checkpoint={favs:{a:value},visited:{}};
function fixture(local={},server={revision:3,favs:{a:{deleted:false,revision:2,value}},visited:{}}){
 const data={taiwan_art_favs:JSON.stringify(local),taiwan_art_visited:'{}'};
 const storage={getItem:k=>data[k]??null,setItem:()=>{throw Error('must never write');}};
 const fetchImpl=async()=>({status:200,ok:true,headers:{get:k=>k==='content-type'?'application/json':'no-store'},json:async()=>server});
 return {data,storage,fetchImpl,checkpoint};
}
test('stale tab loss is reported as a candidate, never automatically restored',async()=>{
 const x=fixture();const before=JSON.stringify(x.data);
 const r=await inspect(x);
 assert.equal(r.status,'review_ready');assert.equal(r.mayRestore,false);assert.equal(r.localLoss,true);
 assert.deepEqual(r.candidates,[{kind:'favs',key:'a',value,item_revision:2}]);
 assert.equal(JSON.stringify(x.data),before);
});
test('server deletion conflicts require review, not resurrection',async()=>{
 const x=fixture({a:value},{revision:4,favs:{a:{deleted:true,revision:4,value:null}},visited:{}});
 const r=await inspect(x);assert.equal(r.status,'review_ready');
 assert.equal(r.candidates.length,0);assert.equal(r.tombstoneConflicts.length,1);
});
test('unauthenticated server response never produces recovery candidates',async()=>{
 const x=fixture();x.fetchImpl=async()=>({status:401,ok:false});
 const r=await inspect(x);assert.equal(r.status,'unauthorized');assert.equal(r.mayRestore,false);
});
test('local state changing during authenticated read fails closed',async()=>{
 const x=fixture();x.fetchImpl=async()=>{x.data.taiwan_art_favs=JSON.stringify({a:value});return {status:200,ok:true,headers:{get:k=>k==='content-type'?'application/json':'no-store'},json:async()=>({revision:3,favs:{a:{deleted:false,revision:2,value}},visited:{}})};};
 const r=await inspect(x);assert.equal(r.status,'local_changed_during_review');assert.equal(r.mayRestore,false);
});
