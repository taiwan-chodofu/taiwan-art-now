const test=require("node:test"),assert=require("node:assert/strict");
const {commit}=require("../static/js/draft_page_action.js");
const fav={title:"台南展",museum:"M",region:"臺南",event:""};
function fixture(){
 const data={taiwan_art_favs:"{}",taiwan_art_visited:"{}"};
 const storage={getItem:k=>data[k]??null,setItem:(k,v)=>{data[k]=v;}};
 let tail=Promise.resolve();
 const locks={request:(_name,_opts,fn)=>{const p=tail.then(fn);tail=p.catch(()=>{});return p;}};
 const events=[];
 return {storage,locks,data,events,onCommitted:x=>events.push(x)};
}
test("two independent page toggles for different exhibitions preserve both",async()=>{
 const x=fixture();
 const results=await Promise.all(["a","b"].map(key=>commit({...x,kind:"favs",key,
   action:"toggle",value:{...fav,title:key}})));
 assert.ok(results.every(r=>r.status==="written_under_cooperative_lock"));
 assert.deepEqual(Object.keys(JSON.parse(x.data.taiwan_art_favs)).sort(),["a","b"]);
 assert.ok(x.events.every(e=>e.action==="set"));
});
test("two simultaneous toggles on same key resolve inside lock, not stale UI",async()=>{
 const x=fixture();
 const results=await Promise.all([commit({...x,kind:"favs",key:"a",action:"toggle",value:fav}),
   commit({...x,kind:"favs",key:"a",action:"toggle",value:fav})]);
 assert.equal(results[1].action,"remove");
 assert.equal(results[1].status,"written_under_cooperative_lock");
 assert.ok(["written_under_cooperative_lock","uncertain_write"].includes(results[0].status));
 if(results[0].status==="uncertain_write")
   assert.equal(x.events.some(e=>e.action==="set"),false);
 assert.deepEqual(JSON.parse(x.data.taiwan_art_favs),{});
});
test("visited ISO and object shapes remain unchanged",async()=>{
 const x=fixture();
 const iso="2026-11-23T00:00:00.000Z";
 await commit({...x,kind:"visited",key:"nearby",action:"toggle",value:iso});
 await commit({...x,kind:"visited",key:"discover",action:"toggle",
   value:{date:iso,title:"A",museum:"M"}});
 const map=JSON.parse(x.data.taiwan_art_visited);
 assert.equal(map.nearby,iso);assert.equal(map.discover.date,iso);
});
test("failed write never invokes committed UI",async()=>{
 const x=fixture();x.storage.setItem=()=>{throw Error("quota");};
 const r=await commit({...x,kind:"favs",key:"a",action:"toggle",value:fav});
 assert.equal(r.status,"unavailable");assert.deepEqual(x.events,[]);
});
test("missing Web Lock fails closed",async()=>{
 const x=fixture();
 const r=await commit({...x,locks:null,kind:"favs",key:"a",action:"toggle",value:fav});
 assert.equal(r.status,"invalid_request");
});
test("explicit remove does not create a tombstone",async()=>{
 const x=fixture();
 const r=await commit({...x,kind:"favs",key:"missing",action:"remove"});
 assert.equal(r.status,"unchanged");
 assert.deepEqual(JSON.parse(x.data.taiwan_art_favs),{});
});

test("cached tab changes exact saved metadata before UI callback: fail closed",async()=>{
 const x=fixture();
 const original=x.storage.getItem;
 let didSet=false,reads=0;
 const set=x.storage.setItem;
 x.storage.setItem=(k,v)=>{set(k,v);didSet=true;};
 x.storage.getItem=k=>{
   const raw=original(k);
   if(k==="taiwan_art_favs"&&didSet&&++reads>=2)
     return JSON.stringify({a:{title:"Overwritten",museum:"M"}});
   return raw;
 };
 const failures=[];
 const r=await commit({...x,kind:"favs",key:"a",action:"toggle",value:fav,
   onFailure:result=>failures.push(result.status)});
 assert.equal(r.status,"uncertain_write");
 assert.deepEqual(x.events,[]);
 assert.deepEqual(failures,["uncertain_write"]);
});
