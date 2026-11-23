const test=require("node:test"),assert=require("node:assert/strict");
const {inspect}=require("../static/js/draft_cutover_preflight.js");
const fav={title:"A",museum:"M"};
const snap=(favs={a:fav},visited={})=>({favs,visited});
function storage(favs={a:fav},visited={}){
 const d={taiwan_art_favs:JSON.stringify(favs),taiwan_art_visited:JSON.stringify(visited)};
 return {getItem:k=>d[k]??null,setItem(){throw Error("read-only");},
   removeItem(){throw Error("read-only");},replace:(kind,value)=>{d["taiwan_art_"+kind]=JSON.stringify(value);}};
}
function fetcher(server,after){
 return async()=>{if(after)after();return {ok:true,status:200,
   headers:{get:k=>k==="content-type"?"application/json":"no-store"},
   json:async()=>server};};
}
const server=(favs={},revision=0)=>({revision,favs,visited:{}});
test("valid checkpoint and authenticated server permit preview only",async()=>{
 const result=await inspect({storage:storage(),checkpoint:snap(),fetchImpl:fetcher(server())});
 assert.equal(result.status,"preflight_ready");assert.equal(result.maySync,true);
 assert.equal(result.proposedAdds,1);assert.equal(result.requiresFreshCAS,true);
});
test("missing checkpoint blocks without network",async()=>{
 let calls=0;
 const result=await inspect({storage:storage(),fetchImpl:async()=>{calls++;}});
 assert.equal(result.status,"checkpoint_required");assert.equal(calls,0);
});
test("cached-tab loss blocks before network and never restores",async()=>{
 const local=storage({});
 let calls=0;
 const result=await inspect({storage:local,checkpoint:snap(),
   fetchImpl:async()=>{calls++;}});
 assert.equal(result.status,"local_review_required");assert.equal(calls,0);
 assert.equal(result.missing[0].key,"a");
});
test("remote explicit tombstone requires review",async()=>{
 const result=await inspect({storage:storage(),checkpoint:snap(),
   fetchImpl:fetcher(server({a:{deleted:true,value:null,revision:1}},1))});
 assert.equal(result.status,"needs_review");assert.equal(result.maySync,false);
 assert.equal(result.review[0].key,"a");
});
test("remote-only active record is preserved",async()=>{
 const result=await inspect({storage:storage(),checkpoint:snap(),
   fetchImpl:fetcher(server({b:{deleted:false,value:fav,revision:1}},1))});
 assert.equal(result.status,"preflight_ready");assert.equal(result.preservedRemote,1);
});
test("local loss during remote read blocks",async()=>{
 const local=storage();
 const result=await inspect({storage:local,checkpoint:snap(),
   fetchImpl:fetcher(server(),()=>local.replace("favs",{}))});
 assert.equal(result.status,"local_review_required");assert.equal(result.maySync,false);
});
test("unauthorized server blocks",async()=>{
 const result=await inspect({storage:storage(),checkpoint:snap(),
   fetchImpl:async()=>({status:403,ok:false})});
 assert.equal(result.status,"unauthorized");assert.equal(result.maySync,false);
});
test("invalid checkpoint cannot authorize sync",async()=>{
 const result=await inspect({storage:storage(),checkpoint:{favs:{a:123},visited:{}},
   fetchImpl:fetcher(server())});
 assert.equal(result.status,"local_review_required");assert.equal(result.maySync,false);
});
