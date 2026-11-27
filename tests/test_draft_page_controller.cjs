const test=require("node:test"),assert=require("node:assert/strict");
const {create}=require("../static/js/draft_page_controller.js");
const fav={title:"台南展",museum:"M",region:"臺南",event:""};
function fixture(){
 const data={taiwan_art_favs:"{}",taiwan_art_visited:"{}"};
 const storage={getItem:k=>data[k]??null,setItem:(k,v)=>{data[k]=v;}};
 let tail=Promise.resolve(),release;
 const locks={request:(_name,_opts,fn)=>{
   const p=tail.then(async()=>{if(release)await new Promise(resolve=>release=resolve);return fn();});
   tail=p.catch(()=>{});return p;
 }};
 const events=[];
 const controller=create({storage,locks,onBusy:x=>events.push("busy:"+x.busy),
   onCommitted:x=>events.push("saved:"+x.action),
   onFailure:x=>events.push("failed:"+x.status)});
 return {data,storage,locks,events,controller,block:()=>{release=()=>{};}};
}
test("favorite toggle UI success follows persistence",async()=>{
 const x=fixture();
 const r=await x.controller.act({kind:"favs",key:"a",action:"toggle",value:fav});
 assert.equal(r.status,"written_under_cooperative_lock");
 assert.deepEqual(x.events,["busy:true","saved:set","busy:false"]);
 assert.equal(JSON.parse(x.data.taiwan_art_favs).a.title,"台南展");
});
test("visited string and object shapes remain intact",async()=>{
 const x=fixture(),date="2026-11-23T00:00:00Z";
 await x.controller.act({kind:"visited",key:"nearby",action:"set",value:date});
 await x.controller.act({kind:"visited",key:"discover",action:"set",value:{date,title:"A",museum:"M"}});
 assert.equal(JSON.parse(x.data.taiwan_art_visited).nearby,date);
 assert.equal(JSON.parse(x.data.taiwan_art_visited).discover.date,date);
});
test("quota failure does not show success",async()=>{
 const x=fixture();x.storage.setItem=()=>{throw Error("quota");};
 const r=await x.controller.act({kind:"favs",key:"a",action:"set",value:fav});
 assert.equal(r.status,"unavailable");
 assert.deepEqual(x.events,["busy:true","failed:unavailable","busy:false"]);
});
test("busy callback failure clears pending slot",async()=>{
 const x=fixture();
 const c=create({storage:x.storage,locks:x.locks,onBusy:({busy})=>{if(busy)throw Error("UI");}});
 assert.equal((await c.act({kind:"favs",key:"a",action:"set",value:fav})).status,"ui_callback_failed");
 assert.equal(c.isBusy("favs","a"),false);
});
test("committed callback failure does not pretend write failed",async()=>{
 const x=fixture();
 const c=create({storage:x.storage,locks:x.locks,onCommitted:()=>{throw Error("UI");}});
 const r=await c.act({kind:"favs",key:"a",action:"set",value:fav});
 assert.equal(r.status,"committed_callback_failed");
 assert.equal(JSON.parse(x.data.taiwan_art_favs).a.title,"台南展");
});
test("same exhibition double click while lock pending is suppressed",async()=>{
 const x=fixture();
 let release;
 const locks={request:(_name,_opts,fn)=>new Promise(resolve=>{release=async()=>resolve(await fn());})};
 const c=create({storage:x.storage,locks});
 const first=c.act({kind:"favs",key:"a",action:"toggle",value:fav});
 assert.equal(c.isBusy("favs","a"),true);
 assert.equal((await c.act({kind:"favs",key:"a",action:"toggle",value:fav})).status,"busy");
 await release();
 assert.equal((await first).status,"written_under_cooperative_lock");
 assert.equal(c.isBusy("favs","a"),false);
});
test("different exhibitions are not globally blocked",async()=>{
 const x=fixture();
 const results=await Promise.all(["a","b"].map(key=>x.controller.act({kind:"favs",key,action:"set",value:{...fav,title:key}})));
 assert.ok(results.every(r=>r.status==="written_under_cooperative_lock"));
 assert.deepEqual(Object.keys(JSON.parse(x.data.taiwan_art_favs)).sort(),["a","b"]);
});
