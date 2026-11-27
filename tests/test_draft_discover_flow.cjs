const test=require("node:test"),assert=require("node:assert/strict");
const {create}=require("../static/js/draft_discover_flow.js");
const {restore}=require("../static/js/draft_explicit_server_restore.js");
const card={stable_key:"a",title:"展覽",museum:"M",dates:"2026",detail_url:"/a",region:"臺南"};
function fixture(){
 const data={taiwan_art_favs:"{}",taiwan_art_visited:"{}"};
 const storage={getItem:k=>data[k]??null,setItem:(k,v)=>{data[k]=v;}};
 let tail=Promise.resolve();
 const locks={request:(_n,_o,fn)=>{const p=tail.then(fn);tail=p.catch(()=>{});return p;}};
 const events=[];
 const flow=create({storage,locks,normalizeKey:s=>s,
   onAdvance:x=>events.push("advance:"+x.action),
   onRestore:x=>events.push("restore:"+x.action),
   onError:x=>events.push("error:"+x.status)});
 return {flow,data,storage,events};
}
test("successful like advances only after verified persistence and undo restores",async()=>{
 const x=fixture();
 assert.equal((await x.flow.swipe(card,"like")).status,"written_under_cooperative_lock");
 assert.equal(JSON.parse(x.data.taiwan_art_favs).a.title,"展覽");
 assert.deepEqual(x.events,["advance:like"]);
 assert.equal((await x.flow.undo()).status,"written_under_cooperative_lock");
 assert.deepEqual(JSON.parse(x.data.taiwan_art_favs),{});
 assert.deepEqual(x.events,["advance:like","restore:like"]);
});
test("quota failure does not advance or record undo",async()=>{
 const x=fixture();x.storage.setItem=()=>{throw Error("quota");};
 assert.equal((await x.flow.swipe(card,"like")).status,"unavailable");
 assert.deepEqual(x.events,["error:unavailable"]);
 assert.equal(x.flow.historySize(),0);
});
test("changed favorite cannot be removed by stale undo",async()=>{
 const x=fixture();
 await x.flow.swipe(card,"like");
 x.data.taiwan_art_favs=JSON.stringify({a:{title:"New metadata",museum:"M"}});
 assert.equal((await x.flow.undo()).status,"stale_undo");
 assert.equal(JSON.parse(x.data.taiwan_art_favs).a.title,"New metadata");
 assert.equal(x.flow.historySize(),1);
 assert.deepEqual(x.events,["advance:like","error:stale_undo"]);
});
test("removed favorite cannot be undone as if it still existed",async()=>{
 const x=fixture();await x.flow.swipe(card,"like");
 x.data.taiwan_art_favs="{}";
 assert.equal((await x.flow.undo()).status,"stale_undo");
 assert.equal(x.flow.historySize(),1);
});
test("skip changes deck without creating favorite or visited",async()=>{
 const x=fixture();
 assert.equal((await x.flow.swipe(card,"skip")).status,"skipped");
 assert.deepEqual(JSON.parse(x.data.taiwan_art_favs),{});
 assert.deepEqual(JSON.parse(x.data.taiwan_art_visited),{});
 assert.equal((await x.flow.undo()).status,"skipped");
 assert.deepEqual(x.events,["advance:skip","restore:skip"]);
});
test("visited object is preserved and undo removes only its exact value",async()=>{
 const x=fixture();await x.flow.swipe(card,"visited");
 assert.equal(JSON.parse(x.data.taiwan_art_visited).a.title,"展覽");
 assert.equal((await x.flow.undo()).status,"written_under_cooperative_lock");
 assert.deepEqual(JSON.parse(x.data.taiwan_art_visited),{});
});
test("busy swipe is suppressed while earlier write waits",async()=>{
 const x=fixture();let release;
 const locks={request:(_n,_o,fn)=>new Promise(resolve=>{release=async()=>resolve(await fn());})};
 const events=[];
 const flow=create({storage:x.storage,locks,normalizeKey:s=>s,onAdvance:()=>events.push("advance")});
 const first=flow.swipe(card,"like");
 assert.equal((await flow.swipe(card,"like")).status,"busy");
 assert.deepEqual(events,[]);
 await release();await first;
 assert.deepEqual(events,["advance"]);
});

for(const [action,storageKey,value] of [
 ["like","taiwan_art_favs",{title:"Earlier title",museum:"Earlier museum",url:"/original"}],
 ["visited","taiwan_art_visited","2026-01-02T00:00:00.000Z"]
]){
 test(action+" preserves an existing registration and undo only restores the card",async()=>{
  const x=fixture();
  const raw=JSON.stringify({a:value});
  x.data[storageKey]=raw;
  let writes=0;
  x.storage.setItem=()=>{writes++;throw Error("must preserve existing entry");};
  const result=await x.flow.swipe(card,action);
  assert.equal(result.preservedExisting,true);
  assert.equal(x.data[storageKey],raw);
  assert.equal((await x.flow.undo()).status,"skipped");
  assert.equal(x.data[storageKey],raw);
  assert.equal(writes,0);
  assert.deepEqual(x.events,["advance:"+action,"restore:"+action]);
 });
}
test("another tab registers while swipe waits for its lock; undo preserves that registration",async()=>{
 const x=fixture();
 const earlier={title:"Other tab",museum:"M"};
 const locks={request:async(_name,_options,callback)=>{
  x.data.taiwan_art_favs=JSON.stringify({a:earlier});
  return callback();
 }};
 const flow=create({storage:x.storage,locks,normalizeKey:s=>s});
 assert.equal((await flow.swipe(card,"like")).preservedExisting,true);
 await flow.undo();
 assert.deepEqual(JSON.parse(x.data.taiwan_art_favs).a,earlier);
});

function serverFixture(){
 let state={revision:0,favs:{},visited:{}},posts=0;
 const response=()=>({ok:true,status:200,headers:{get:k=>k==='content-type'?'application/json':'no-store'},json:async()=>structuredClone(state)});
 const fetchImpl=async(_,options)=>{
  if(options.method==='POST'){
   posts++;
   const body=JSON.parse(options.body);
   assert.equal(body.base_revision,state.revision);
   const revision=++state.revision;
   for(const kind of ['favs','visited'])for(const [key,op] of Object.entries(body.changes[kind]))
    state[kind][key]={revision,deleted:!!op.delete,value:op.delete?null:op.set};
  }
  return response();
 };
 return {fetchImpl,get state(){return state;},get posts(){return posts;}};
}
test('server Discover saves and undoes want while preserving seen',async()=>{
 const server=serverFixture(),events=[];
 const flow=create({fetchImpl:server.fetchImpl,normalizeKey:s=>s,
  onAdvance:()=>events.push('advance'),onRestore:()=>events.push('restore')});
 await flow.swipe(card,'visited');
 await flow.swipe(card,'like');
 await flow.undo();
 assert.equal(server.state.favs.a.deleted,true);
 assert.equal(server.state.visited.a.deleted,false);
 assert.deepEqual(events,['advance','advance','restore']);
});
test('server undo rejects a newer registration with identical metadata',async()=>{
 const server=serverFixture();
 const flow=create({fetchImpl:server.fetchImpl,normalizeKey:s=>s});
 await flow.swipe(card,'like');
 server.state.revision++;
 server.state.favs.a.revision=server.state.revision;
 assert.equal((await flow.undo()).status,'stale_undo');
 assert.equal(server.posts,1);
});
test('lost server reply locks Discover without advancing or retrying even on skip',async()=>{
 const server=serverFixture(),events=[];
 const flow=create({normalizeKey:s=>s,onAdvance:()=>events.push('advance'),
  fetchImpl:async(path,options)=>{
   const result=await server.fetchImpl(path,options);
   if(options.method==='POST')throw Error('lost reply');
   return result;
  }});
 assert.equal((await flow.swipe(card,'like')).status,'write_outcome_unknown');
 assert.equal((await flow.swipe(card,'like')).status,'unknown_commit');
 assert.equal((await flow.swipe(card,'skip')).status,'unknown_commit');
 assert.equal(server.posts,1);
 assert.equal(flow.historySize(),0);
 assert.deepEqual(events,[]);
});
test('recover stays locked when global revision has not moved past the uncertain write',async()=>{
 const server=serverFixture();
 let dropNextPost=true;
 const flow=create({normalizeKey:s=>s,fetchImpl:async(path,options)=>{
  // Simulate the request never reaching the server at all (not merely a lost
  // reply after a successful commit), so revision genuinely never advances.
  if(options.method==='POST'&&dropNextPost){dropNextPost=false;throw Error('network error');}
  return server.fetchImpl(path,options);
 }});
 assert.equal((await flow.swipe(card,'like')).status,'write_outcome_unknown');
 assert.equal(flow.isUncertain(),true);
 assert.equal(server.state.revision,0);
 assert.equal((await flow.recover()).status,'still_unknown_commit');
 assert.equal(flow.isUncertain(),true);
 assert.equal((await flow.swipe(card,'skip')).status,'unknown_commit');
});
test('recover clears the lock once global revision has advanced past the attempted write',async()=>{
 const server=serverFixture();
 let dropNextPost=true;
 const flow=create({normalizeKey:s=>s,fetchImpl:async(path,options)=>{
  const result=await server.fetchImpl(path,options);
  if(options.method==='POST'&&dropNextPost){dropNextPost=false;throw Error('lost reply');}
  return result;
 }});
 assert.equal((await flow.swipe(card,'like')).status,'write_outcome_unknown');
 server.state.revision++;
 const recovered=await flow.recover();
 assert.equal(recovered.status,'recovered');
 assert.equal(recovered.revision,server.state.revision);
 assert.equal(flow.isUncertain(),false);
 const second=await flow.swipe(card,'visited');
 assert.equal(second.status,'written_under_cooperative_lock');
});
test('recover is a no-op outside the uncertain state and unavailable without fetchImpl',async()=>{
 const server=serverFixture();
 const serverFlow=create({normalizeKey:s=>s,fetchImpl:server.fetchImpl});
 assert.equal((await serverFlow.recover()).status,'not_uncertain');
 const x=fixture();
 assert.equal((await x.flow.recover()).status,'not_applicable');
});
test('disposed flow refuses to swipe, undo, clearHistory or recover',async()=>{
 const x=fixture();
 await x.flow.swipe(card,'like');
 x.flow.dispose();
 assert.equal((await x.flow.swipe(card,'visited')).status,'disposed');
 assert.equal((await x.flow.undo()).status,'disposed');
 assert.equal(x.flow.clearHistory().status,'disposed');
 assert.equal((await x.flow.recover()).status,'disposed');
});

function restoreCapableServerFixture(){
 let state={revision:0,favs:{},visited:{}},posts=0,issued=null;
 const response=()=>({ok:true,status:200,
  headers:{get:k=>k==='content-type'?'application/json':'no-store'},
  json:async()=>structuredClone(state)});
 const fetchImpl=async(path,options)=>{
  if(options.method!=='POST')return response();
  posts++;
  if(path.endsWith('/review/keep/issue')){
   const body=JSON.parse(options.body);
   assert.equal(body.base_revision,state.revision);
   issued={token:'tok-'+posts,kind:body.kind,key:body.key,local_value:body.local_value};
   return {ok:true,status:200,
    headers:{get:k=>k==='content-type'?'application/json':'no-store'},
    json:async()=>({token:issued.token})};
  }
  if(path.endsWith('/review/keep/consume')){
   const body=JSON.parse(options.body);
   assert.equal(body.token,issued&&issued.token);
   const revision=++state.revision;
   state[issued.kind][issued.key]={revision,deleted:false,value:body.local_value};
   issued=null;
   return response();
  }
  const body=JSON.parse(options.body);
  assert.equal(body.base_revision,state.revision);
  const revision=++state.revision;
  for(const kind of ['favs','visited'])for(const [key,op] of Object.entries(body.changes[kind]))
   state[kind][key]={revision,deleted:!!op.delete,value:op.delete?null:op.set};
  return response();
 };
 return {fetchImpl,get state(){return state;},get posts(){return posts;}};
}
test('swiping a tombstoned card advances without resurrecting it, and its undo is card-only',async()=>{
 const server=restoreCapableServerFixture(),events=[];
 server.state.favs.a={revision:1,deleted:true,value:null};
 server.state.revision=1;
 const flow=create({fetchImpl:server.fetchImpl,normalizeKey:s=>s,restoreImpl:restore,
  onAdvance:()=>events.push('advance'),onError:x=>events.push('error:'+x.status)});
 const result=await flow.swipe(card,'like');
 assert.equal(result.status,'needs_restore_review');
 assert.deepEqual(events,['advance']);
 assert.equal(server.posts,0);
 assert.equal(server.state.favs.a.deleted,true);
 assert.equal((await flow.undo()).status,'skipped');
 assert.equal(server.posts,0);
 assert.equal(server.state.favs.a.deleted,true);
});
test('confirmRestore resurrects a tombstone only on explicit call, and normal undo removes it afterward',async()=>{
 const server=restoreCapableServerFixture(),events=[];
 server.state.favs.a={revision:1,deleted:true,value:null};
 server.state.revision=1;
 const flow=create({fetchImpl:server.fetchImpl,normalizeKey:s=>s,restoreImpl:restore,
  onAdvance:()=>events.push('advance')});
 await flow.swipe(card,'like');
 const restored=await flow.confirmRestore(card,'like');
 assert.equal(restored.status,'written_under_cooperative_lock');
 assert.equal(server.state.favs.a.deleted,false);
 assert.equal(server.state.favs.a.value.title,'展覽');
 assert.deepEqual(events,['advance','advance']);
 assert.equal((await flow.undo()).status,'written_under_cooperative_lock');
 assert.equal(server.state.favs.a.deleted,true);
});
test('confirmRestore refuses an item that is not actually tombstoned, and requires restoreImpl',async()=>{
 const server=restoreCapableServerFixture();
 const flow=create({fetchImpl:server.fetchImpl,normalizeKey:s=>s,restoreImpl:restore});
 assert.equal((await flow.confirmRestore(card,'like')).status,'not_tombstoned');
 const noRestoreImpl=create({fetchImpl:server.fetchImpl,normalizeKey:s=>s});
 assert.equal((await noRestoreImpl.confirmRestore(card,'like')).status,'not_applicable');
 const x=fixture();
 assert.equal((await x.flow.confirmRestore(card,'like')).status,'not_applicable');
});
test('a second swipe sharing a normalized key with an already-live registration cannot undo that registration',async()=>{
 // Guards the createdRevisions/history ownership model: two distinct card
 // objects whose stable_key normalizes to the identical key (the exact risk
 // documented in DECISIONS.md 2026-11-26 for the legacy lossy normalizer)
 // must never let the second swipe's undo delete the first swipe's write.
 const server=restoreCapableServerFixture();
 const cardA={stable_key:"a",title:"Card A",museum:"M",dates:"2026",detail_url:"/a",region:"R"};
 const cardB={stable_key:"a",title:"Card B (collides with A under normalizeKey)",museum:"M",dates:"2026",detail_url:"/b",region:"R"};
 const flow=create({fetchImpl:server.fetchImpl,normalizeKey:s=>s});
 const first=await flow.swipe(cardA,'like');
 assert.equal(first.status,'written_under_cooperative_lock');
 const second=await flow.swipe(cardB,'like');
 assert.equal(second.status,'skipped');
 assert.equal(second.preservedExisting,true);
 const undoSecond=await flow.undo();
 assert.equal(undoSecond.status,'skipped');
 assert.equal(server.state.favs.a.deleted,false);
 assert.equal(server.state.favs.a.value.title,'Card A');
 const undoFirst=await flow.undo();
 assert.equal(undoFirst.status,'written_under_cooperative_lock');
 assert.equal(server.state.favs.a.deleted,true);
});
