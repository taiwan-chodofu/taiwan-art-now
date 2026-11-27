const test=require('node:test'),assert=require('node:assert/strict');
const {create}=require('../static/js/draft_legacy_migration_bootstrap.js');
const response=(state,status=200)=>({ok:status===200,status,
 headers:{get:k=>k==='content-type'?'application/json':'no-store'},json:async()=>state});
function serverFixture(initial={revision:0,favs:{},visited:{}}){
 let state=initial,posts=0,gets=0;
 const fetchImpl=async(path,opts)=>{
  if(opts.method==='GET'){gets++;return response(state);}
  posts++;
  const {base_revision,changes}=JSON.parse(opts.body);
  if(base_revision!==state.revision)return response({},409);
  const next=state.revision+1;
  state={...state,revision:next,favs:{...state.favs},visited:{...state.visited}};
  for(const kind of ['favs','visited'])for(const [key,op] of Object.entries(changes[kind]))
   state[kind][key]={revision:next,deleted:!!op.delete,value:op.delete?null:op.set};
  return response(state);
 };
 return {fetchImpl,get posts(){return posts;},get gets(){return gets;},
  get state(){return state;},set state(v){state=v;}};
}
function storageFixture(data={}){
 const map={...data};
 return {getItem:k=>(k in map?map[k]:null),setItem:(k,v)=>{map[k]=v;}};
}
test('nothing to migrate when local storage is empty, no network touched',async()=>{
 const server=serverFixture();
 const storage=storageFixture({taiwan_art_favs:'{}',taiwan_art_visited:'{}'});
 const bootstrap=create({fetchImpl:server.fetchImpl,storage});
 assert.deepEqual(await bootstrap.run(),{status:'nothing_to_migrate'});
 assert.equal(server.gets,0);assert.equal(server.posts,0);
});
test('local-only entries are added without any review',async()=>{
 const server=serverFixture();
 const storage=storageFixture({
  taiwan_art_favs:JSON.stringify({a:{title:'A',museum:'M'},b:{title:'B',museum:'M'}}),
  taiwan_art_visited:'{}'});
 const bootstrap=create({fetchImpl:server.fetchImpl,storage});
 const result=await bootstrap.run();
 assert.equal(result.status,'ready');
 assert.equal(result.submitted,2);
 assert.equal(result.revision,2);
 assert.deepEqual(result.review.items,[]);
 assert.equal(server.state.favs.a.deleted,false);
 assert.equal(server.state.favs.a.value.title,'A');assert.equal(server.state.favs.a.value.museum,'M');
 assert.equal(server.state.favs.b.deleted,false);
});
test('a server tombstone is surfaced for review, never added',async()=>{
 const server=serverFixture({revision:2,favs:{a:{revision:2,deleted:true,value:null}},visited:{}});
 const storage=storageFixture({
  taiwan_art_favs:JSON.stringify({a:{title:'Old favorite',museum:'M'}}),taiwan_art_visited:'{}'});
 const bootstrap=create({fetchImpl:server.fetchImpl,storage});
 const result=await bootstrap.run();
 assert.equal(result.status,'ready');
 assert.equal(result.submitted,0);
 assert.equal(server.posts,0);
 assert.equal(result.review.items.length,1);
 assert.equal(result.review.items[0].status,'deleted_remotely');
 assert.equal(result.review.items[0].kind,'favs');
 assert.equal(result.review.items[0].key,'a');
 assert.deepEqual(result.review.items[0].options.map(o=>o.id),['keep_deleted','request_restore']);
});
test('an existing non-deleted server value silently wins, never overwritten',async()=>{
 const server=serverFixture({revision:1,favs:{a:{revision:1,deleted:false,value:{title:'Fresh',museum:'M'}}},visited:{}});
 const storage=storageFixture({
  taiwan_art_favs:JSON.stringify({a:{title:'Stale',museum:'M'}}),taiwan_art_visited:'{}'});
 const bootstrap=create({fetchImpl:server.fetchImpl,storage});
 const result=await bootstrap.run();
 assert.equal(result.submitted,0);
 assert.equal(server.posts,0);
 assert.deepEqual(result.review.items,[]);
 assert.deepEqual(server.state.favs.a.value,{title:'Fresh',museum:'M'});
});
test('a stale revision mid-batch stops the batch without retrying',async()=>{
 const server=serverFixture();
 const storage=storageFixture({
  taiwan_art_favs:JSON.stringify({a:{title:'A',museum:'M'},b:{title:'B',museum:'M'}}),
  taiwan_art_visited:'{}'});
 // The first add commits normally. Simulate another device's concurrent
 // write landing exactly between the two adds by rejecting only the SECOND
 // POST with a 409, regardless of the base_revision it carries -- this is
 // what a real race would look like from the writer's point of view.
 let postCount=0;
 const racingFetch=async(path,opts)=>{
  if(opts.method==='POST'){
   postCount++;
   if(postCount===2)return response({},409);
  }
  return server.fetchImpl(path,opts);
 };
 const bootstrap=create({fetchImpl:racingFetch,storage});
 const result=await bootstrap.run();
 assert.equal(result.status,'partial');
 assert.equal(result.submitted,1);
 assert.equal(result.failure,'stale_revision');
 assert.equal(server.posts,1); // only the first add ever actually reached the server
});
test('resolveReviewItem keep_deleted makes no network call',async()=>{
 const server=serverFixture();
 const storage=storageFixture({taiwan_art_favs:'{}',taiwan_art_visited:'{}'});
 const bootstrap=create({fetchImpl:server.fetchImpl,storage});
 const result=await bootstrap.resolveReviewItem({kind:'favs',key:'a',choice:'keep_deleted'});
 assert.deepEqual(result,{status:'kept_deleted',committed:false});
 assert.equal(server.gets,0);assert.equal(server.posts,0);
});
test('resolveReviewItem request_restore calls restoreImpl with the local value and current revision',async()=>{
 const server=serverFixture({revision:3,favs:{a:{revision:3,deleted:true,value:null}},visited:{}});
 const storage=storageFixture({
  taiwan_art_favs:JSON.stringify({a:{title:'Old favorite',museum:'M'}}),taiwan_art_visited:'{}'});
 let captured=null;
 const restoreImpl=async(args)=>{captured=args;return {status:'server_confirmed',committed:true,revision:4};};
 const bootstrap=create({fetchImpl:server.fetchImpl,storage,restoreImpl});
 const result=await bootstrap.resolveReviewItem({kind:'favs',key:'a',choice:'request_restore'});
 assert.deepEqual(result,{status:'server_confirmed',committed:true,revision:4});
 assert.equal(captured.kind,'favs');assert.equal(captured.key,'a');
 assert.equal(captured.value.title,'Old favorite');assert.equal(captured.value.museum,'M');
 assert.equal(captured.reviewedRevision,3);assert.equal(captured.tombstoneRevision,3);
 assert.equal(captured.confirmed,true);
});
test('resolveReviewItem is expired once the tombstone is no longer there',async()=>{
 const server=serverFixture({revision:1,favs:{},visited:{}}); // never tombstoned at all
 const storage=storageFixture({
  taiwan_art_favs:JSON.stringify({a:{title:'Old favorite',museum:'M'}}),taiwan_art_visited:'{}'});
 let called=false;
 const restoreImpl=async()=>{called=true;return {status:'server_confirmed',committed:true};};
 const bootstrap=create({fetchImpl:server.fetchImpl,storage,restoreImpl});
 const result=await bootstrap.resolveReviewItem({kind:'favs',key:'a',choice:'request_restore'});
 assert.deepEqual(result,{status:'review_expired',committed:false});
 assert.equal(called,false);
});
test('dispose blocks run and resolveReviewItem',async()=>{
 const server=serverFixture();
 const storage=storageFixture({
  taiwan_art_favs:JSON.stringify({a:{title:'A',museum:'M'}}),taiwan_art_visited:'{}'});
 const bootstrap=create({fetchImpl:server.fetchImpl,storage});
 bootstrap.dispose();
 assert.deepEqual(await bootstrap.run(),{status:'disposed'});
 assert.deepEqual(await bootstrap.resolveReviewItem({kind:'favs',key:'a',choice:'request_restore'}),
  {status:'disposed',committed:false});
 assert.equal(server.gets,0);assert.equal(server.posts,0);
});
test('invalid local storage data fails closed without touching the network',async()=>{
 const server=serverFixture();
 const storage=storageFixture({taiwan_art_favs:'not json',taiwan_art_visited:'{}'});
 const bootstrap=create({fetchImpl:server.fetchImpl,storage});
 assert.deepEqual(await bootstrap.run(),{status:'invalid_local',kind:'favs'});
 assert.equal(server.gets,0);assert.equal(server.posts,0);
});
