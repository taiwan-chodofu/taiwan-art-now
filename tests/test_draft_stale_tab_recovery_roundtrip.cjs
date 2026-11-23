/* Synthetic stale-tab loss and explicit authenticated recovery roundtrip.
 * Demonstrates recovery is possible with a surviving server record, NOT that
 * cached tabs are prevented from overwriting localStorage again.
 */
const test=require('node:test'),assert=require('node:assert/strict');
const {inspect}=require('../static/js/draft_authenticated_recovery_review.js');
const {restore}=require('../static/js/draft_authenticated_guarded_restore.js');
const {inspect:detectLoss}=require('../static/js/draft_loss_detector.js');
const fav={title:'Exhibition',museum:'Museum'};
const visited='2026-11-23T00:00:00Z';
function fixture(){
 const data={taiwan_art_favs:JSON.stringify({a:fav}),taiwan_art_visited:JSON.stringify({a:visited})};
 const storage={getItem:k=>data[k]??null,setItem:(k,v)=>{data[k]=v;}};
 const server={revision:7,favs:{a:{deleted:false,revision:3,value:fav}},visited:{a:{deleted:false,revision:5,value:visited}}};
 const fetchImpl=async()=>({status:200,ok:true,headers:{get:k=>k==='content-type'?'application/json':'no-store'},json:async()=>server});
 const locks={request:(_name,_opts,fn)=>fn()};
 return {data,storage,server,fetchImpl,locks,checkpoint:{favs:{a:fav},visited:{a:visited}}};
}
test('legacy tab erases both maps; reviewed independent flags can be restored one by one',async()=>{
 const x=fixture();
 // Simulate an already-open cached page writing its stale whole-map snapshot.
 x.data.taiwan_art_favs='{}';x.data.taiwan_art_visited='{}';
 const review=await inspect(x);
 assert.equal(review.status,'review_ready');assert.equal(review.localLoss,true);
 assert.equal(review.candidates.length,2);
 assert.deepEqual(review.candidates.map(c=>c.kind).sort(),['favs','visited']);
 for(const candidate of review.candidates){
  const r=await restore({...x,expectedRevision:review.base_revision,
   reviewedCandidates:review.candidates,decision:{kind:candidate.kind,key:candidate.key,choice:'restore'},confirmed:true});
  assert.equal(r.status,'restored_under_cooperative_lock');
 }
 assert.equal(JSON.parse(x.data.taiwan_art_favs).a.title,'Exhibition');
 assert.equal(JSON.parse(x.data.taiwan_art_visited).a,visited);
 assert.equal(detectLoss({storage:x.storage,checkpoint:x.checkpoint}).status,'consistent');
 // The old tab remains unsafe. A subsequent stale whole-map write can erase again.
 x.data.taiwan_art_favs='{}';
 assert.equal(detectLoss({storage:x.storage,checkpoint:x.checkpoint}).status,'needs_review');
});
test('server tombstone is not restored even if checkpoint remembers it',async()=>{
 const x=fixture();x.data.taiwan_art_favs='{}';
 x.server.favs.a={deleted:true,revision:6,value:null};
 const review=await inspect(x);
 assert.equal(review.candidates.some(c=>c.kind==='favs'),false);
 assert.equal(JSON.parse(x.data.taiwan_art_favs).a,undefined);
});
