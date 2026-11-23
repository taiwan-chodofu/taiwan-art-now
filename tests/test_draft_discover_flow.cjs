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
