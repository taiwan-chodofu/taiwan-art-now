const test=require("node:test"),assert=require("node:assert/strict");
const {create}=require("../static/js/draft_detail_action_adapter.js");
function fixture(fail=false){
 const data={taiwan_art_favs:"{}",taiwan_art_visited:"{}"},events=[];
 const storage={getItem:k=>data[k]??null,setItem:(k,v)=>{if(fail)throw Error("quota");data[k]=v;}};
 const locks={request:(_name,_opts,fn)=>Promise.resolve().then(fn)};
 const adapter=create({storage,locks,key:"ex_1",metadata:{title:"展覽",museum:"M",dates:"2026",url:"/ex"},
  now:()=>"2026-11-23T00:00:00.000Z",onRender:x=>events.push(["render",x]),
  onAnalytics:x=>events.push(["analytics",x]),onNotify:x=>events.push(["notify",x]),
  onFailure:x=>events.push(["failure",x])});
 return {data,events,adapter};
}
test("detail want and seen are independent; callbacks follow persistence",async()=>{
 const x=fixture();
 assert.equal((await x.adapter.toggle("favs")).status,"written_under_cooperative_lock");
 assert.equal((await x.adapter.toggle("visited")).status,"written_under_cooperative_lock");
 assert.deepEqual(x.events.map(e=>e[0]),["render","analytics","notify","render","analytics","notify"]);
 assert.equal(x.events[1][1].event,"add_to_favorites");
 assert.equal(x.events[4][1].event,"mark_visited");
 assert.equal(JSON.parse(x.data.taiwan_art_visited).ex_1,"2026-11-23T00:00:00.000Z");
 assert.ok(JSON.parse(x.data.taiwan_art_favs).ex_1);
 assert.equal((await x.adapter.toggle("visited")).action,"remove");
 assert.ok(JSON.parse(x.data.taiwan_art_favs).ex_1);
});
test("detail quota failure never renders, tracks analytics or syncs",async()=>{
 const x=fixture(true);const r=await x.adapter.toggle("favs");
 assert.equal(r.status,"unavailable");
 assert.deepEqual(x.events.map(e=>e[0]),["failure"]);
 assert.deepEqual(JSON.parse(x.data.taiwan_art_favs),{});
});

test("detail unavailable Web Locks never announce a saved bookmark",async()=>{
 const x=fixture();
 const adapter=create({storage:{getItem:k=>x.data[k]??null,setItem:(k,v)=>{x.data[k]=v;}},
  locks:null,key:"ex_1",metadata:{title:"展覽",museum:"M"},
  onRender:()=>x.events.push(["render"]),onAnalytics:()=>x.events.push(["analytics"]),
  onNotify:()=>x.events.push(["notify"]),onFailure:failure=>x.events.push(["failure",failure])});
 const result=await adapter.toggle("favs");
 assert.equal(result.status,"not_authorized");
 assert.deepEqual(x.events.map(e=>e[0]),["failure"]);
 assert.deepEqual(JSON.parse(x.data.taiwan_art_favs),{});
});

test("rapid repeated detail taps do not toggle twice while first write is pending",async()=>{
 const data={taiwan_art_favs:"{}",taiwan_art_visited:"{}"},events=[];
 let release;
 const gate=new Promise(resolve=>{release=resolve;});
 const storage={getItem:k=>data[k]??null,setItem:(k,v)=>{data[k]=v;}};
 const locks={request:async(_name,_opts,fn)=>{await gate;return fn();}};
 const adapter=create({storage,locks,key:"ex_1",metadata:{title:"展覽",museum:"M"},
  onRender:()=>events.push("render"),onAnalytics:()=>events.push("analytics"),
  onNotify:()=>events.push("notify")});
 const first=adapter.toggle("favs");
 const second=await adapter.toggle("favs");
 assert.equal(second.status,"busy");
 assert.deepEqual(events,[]);
 assert.deepEqual(JSON.parse(data.taiwan_art_favs),{});
 release();
 assert.equal((await first).status,"written_under_cooperative_lock");
 assert.ok(JSON.parse(data.taiwan_art_favs).ex_1);
 assert.deepEqual(events,["render","analytics","notify"]);
});

test("independent detail buttons retain both states when writes are serialized",async()=>{
 const x=fixture();
 const results=await Promise.all([x.adapter.toggle("favs"),x.adapter.toggle("visited")]);
 assert.deepEqual(results.map(r=>r.status),["written_under_cooperative_lock","written_under_cooperative_lock"]);
 assert.ok(JSON.parse(x.data.taiwan_art_favs).ex_1);
 assert.ok(JSON.parse(x.data.taiwan_art_visited).ex_1);
});

test("navigation disposal suppresses stale UI, analytics and notification callbacks",async()=>{
 const data={taiwan_art_favs:"{}",taiwan_art_visited:"{}"},events=[];
 let release;const gate=new Promise(resolve=>{release=resolve;});
 const storage={getItem:k=>data[k]??null,setItem:(k,v)=>{data[k]=v;}};
 const locks={request:async(_name,_opts,fn)=>{await gate;return fn();}};
 const adapter=create({storage,locks,key:"ex_1",metadata:{title:"展覽",museum:"M"},
  onRender:()=>events.push("render"),onAnalytics:()=>events.push("analytics"),
  onNotify:()=>events.push("notify"),onFailure:()=>events.push("failure"),
  onBusy:()=>events.push("busy")});
 const pending=adapter.toggle("favs");
 adapter.dispose();
 assert.equal((await adapter.toggle("visited")).status,"disposed");
 release();
 assert.equal((await pending).status,"written_under_cooperative_lock");
 assert.ok(JSON.parse(data.taiwan_art_favs).ex_1);
 assert.deepEqual(events,["busy"]);
});
