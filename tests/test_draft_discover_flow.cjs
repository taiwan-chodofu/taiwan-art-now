const test=require("node:test"),assert=require("node:assert/strict");
const {create}=require("../static/js/draft_discover_flow.js");
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
