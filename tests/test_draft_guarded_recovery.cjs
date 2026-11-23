const test=require("node:test"),assert=require("node:assert/strict");
const {restore}=require("../static/js/draft_guarded_recovery.js");
const {plan}=require("../static/js/draft_server_recovery.js");
const fav={title:"A",museum:"M"};
function fixture(){
 const data={taiwan_art_favs:JSON.stringify({other:{title:"Other",museum:"M"}}),taiwan_art_visited:"{}"};
 const storage={getItem:k=>data[k]??null,setItem:(k,v)=>{data[k]=v;}};
 const locks={request:async(name,options,fn)=>fn()};
 const server={revision:1,favs:{a:{deleted:false,revision:1,value:fav}},visited:{}};
 const reviewedCandidates=plan({storage,serverState:server}).candidates;
 return {data,storage,locks,server,reviewedCandidates,decision:{kind:"favs",key:"a",choice:"restore"}};
}
function args(x){return {storage:x.storage,locks:x.locks,fetchFreshState:async()=>x.server,
 expectedRevision:1,reviewedCandidates:x.reviewedCandidates,decision:x.decision,confirmed:true};}
test("explicit confirmed restore adds only selected item",async()=>{
 const x=fixture(),r=await restore(args(x));
 assert.equal(r.status,"restored_under_cooperative_lock");
 assert.deepEqual(JSON.parse(x.data.taiwan_art_favs),{other:{title:"Other",museum:"M"},a:fav});
});
test("unconfirmed choice makes no changes",async()=>{
 const x=fixture(),r=await restore({...args(x),confirmed:false});
 assert.equal(r.status,"not_authorized");assert.equal(JSON.parse(x.data.taiwan_art_favs).a,undefined);
});
test("missing Web Locks fails closed",async()=>{
 const x=fixture();assert.equal((await restore({...args(x),locks:null})).status,"not_authorized");
});
test("server revision change blocks restore",async()=>{
 const x=fixture();x.server.revision=2;
 assert.equal((await restore(args(x))).status,"stale_server");
});
test("server tombstone blocks restore",async()=>{
 const x=fixture();x.server.favs.a={deleted:true,revision:1,value:null};
 assert.equal((await restore(args(x))).status,"stale_review");
});
test("existing local item never overwritten",async()=>{
 const x=fixture();x.data.taiwan_art_favs=JSON.stringify({a:{title:"Local",museum:"M"}});
 assert.equal((await restore(args(x))).status,"stale_review");
 assert.equal(JSON.parse(x.data.taiwan_art_favs).a.title,"Local");
});
test("network failure blocks restore",async()=>{
 const x=fixture();assert.equal((await restore({...args(x),fetchFreshState:async()=>{throw Error("offline");}})).status,"unavailable");
});
test("quota failure never claims restored",async()=>{
 const x=fixture();x.storage.setItem=()=>{throw Error("quota");};
 assert.equal((await restore(args(x))).status,"unavailable");
});
test("silent failed write is detected",async()=>{
 const x=fixture();x.storage.setItem=()=>{};
 assert.equal((await restore(args(x))).status,"uncertain_write");
});
test("legacy tab mutation during guarded read blocks restore",async()=>{
 const x=fixture();let count=0;
 const original=x.storage.getItem;
 x.storage.getItem=k=>{
   if(k==="taiwan_art_favs"&&++count===3)
     x.data.taiwan_art_favs=JSON.stringify({older:{title:"Older",museum:"M"}});
   return original(k);
 };
 const r=await restore(args(x));
 assert.equal(r.status,"stale_local");
 assert.equal(JSON.parse(x.data.taiwan_art_favs).a,undefined);
});
