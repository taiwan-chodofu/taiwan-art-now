const test=require("node:test");
const assert=require("node:assert/strict");
const {run,PATH}=require("../static/js/draft_additive_retry.js");
const fav={title:"A",museum:"M",dates:"2026",url:""};
const item=(value,revision=1,deleted=false)=>({value,revision,deleted});
const state=(revision=0,favs={},visited={})=>({revision,favs,visited});
function storage(favs={a:fav},visited={}){
 const data={taiwan_art_favs:JSON.stringify(favs),taiwan_art_visited:JSON.stringify(visited)};
 return {getItem:k=>data[k]??null,setItem(){throw Error("no writes");},
   removeItem(){throw Error("no writes");},
   change(k,v){data[k]=JSON.stringify(v);}};
}
function response(body,status=200){
 return {status,ok:status>=200&&status<300,
   headers:{get:k=>k==="content-type"?"application/json":k==="cache-control"?"no-store":null},
   json:async()=>body};
}
test("stale revision re-fetches and preserves remote favorite with local addition",async()=>{
 const local=storage({a:fav});
 const calls=[];
 const remote=state(1,{b:item({title:"B"})});
 const saved=state(2,{b:item({title:"B"}),a:item(fav,2)});
 const fetchImpl=async(path,opts)=>{
   calls.push({path,opts});
   if(opts.method==="GET")return response(calls.filter(c=>c.opts.method==="GET").length===1
     ?state():remote);
   return response(calls.filter(c=>c.opts.method==="POST").length===1
     ?{error:"stale_revision"}:saved,
     calls.filter(c=>c.opts.method==="POST").length===1?409:200);
 };
 const result=await run({storage:local,fetchImpl});
 assert.equal(result.status,"saved");
 assert.equal(result.retried,true);
 assert.equal(calls.filter(c=>c.opts.method==="POST").length,2);
 assert.equal(JSON.parse(calls[3].opts.body).base_revision,1);
 assert.equal(JSON.parse(calls[3].opts.body).changes.favs.a.set.title,"A");
 assert.equal(result.preservedRemote[0].key,"b");
});
test("explicit tombstone after stale 409 blocks retry and does not POST again",async()=>{
 let posts=0,gets=0;
 const fetchImpl=async(path,opts)=>{
   if(opts.method==="GET")return response(++gets===1?state():state(1,{a:item(null,1,true)}));
   posts++;return response({},409);
 };
 const result=await run({storage:storage(),fetchImpl});
 assert.equal(result.status,"needs_review");
 assert.equal(result.review[0].key,"a");
 assert.equal(posts,1);
});
test("remote-only records do not trigger a write",async()=>{
 let posts=0;
 const result=await run({storage:storage({}),fetchImpl:async(path,opts)=>{
   if(opts.method==="POST")posts++;
   return response(state(1,{b:item(fav)}));
 }});
 assert.equal(result.status,"up_to_date");
 assert.equal(posts,0);
});
test("local mutation after 409 stops automatic retry",async()=>{
 const local=storage();
 let posts=0;
 const result=await run({storage:local,fetchImpl:async(path,opts)=>{
   if(opts.method==="GET")return response(state());
   posts++;local.change("taiwan_art_favs",{a:fav,b:fav});
   return response({},409);
 }});
 assert.equal(result.status,"local_changed");
 assert.equal(posts,1);
});
test("second 409 stops bounded retry",async()=>{
 let posts=0;
 const result=await run({storage:storage(),fetchImpl:async(path,opts)=>{
   if(opts.method==="GET")return response(state(posts));
   posts++;return response({},409);
 }});
 assert.equal(result.status,"stale_revision");
 assert.equal(posts,2);
});
test("ambiguous network POST failure does not retry",async()=>{
 let posts=0;
 const result=await run({storage:storage(),fetchImpl:async(path,opts)=>{
   if(opts.method==="GET")return response(state());
   posts++;throw Error("offline");
 }});
 assert.equal(result.status,"unknown_commit");
 assert.equal(posts,1);
});
test("invalid authenticated response never posts",async()=>{
 let posts=0;
 const result=await run({storage:storage(),fetchImpl:async(path,opts)=>{
   if(opts.method==="POST")posts++;
   return {...response(state()),headers:{get:()=> "text/html"}};
 }});
 assert.equal(result.status,"invalid_response");
 assert.equal(posts,0);
});
test("unexpected POST payload is not acknowledged as saved",async()=>{
 const result=await run({storage:storage(),fetchImpl:async(path,opts)=>
   response(opts.method==="GET"?state():state(1))});
 assert.equal(result.status,"unknown_commit");
});

test("checkpoint loss before initial GET blocks all network writes",async()=>{
 let calls=0;
 const result=await run({storage:storage({}),checkpoint:{favs:{a:fav},visited:{}},
   fetchImpl:async()=>{calls++;return response(state());}});
 assert.equal(result.status,"local_review_required");
 assert.equal(result.missing[0].key,"a");
 assert.equal(calls,0);
});
test("checkpoint loss during authenticated GET blocks POST",async()=>{
 const local=storage();
 let posts=0;
 const result=await run({storage:local,checkpoint:{favs:{a:fav},visited:{}},
   fetchImpl:async(path,opts)=>{
     if(opts.method==="GET"){local.change("taiwan_art_favs",{});return response(state());}
     posts++;return response(state(1));
   }});
 assert.equal(result.status,"local_review_required");
 assert.equal(posts,0);
});
test("checkpoint loss between stale 409 and retry blocks another POST",async()=>{
 const local=storage();
 let posts=0;
 const result=await run({storage:local,checkpoint:{favs:{a:fav},visited:{}},
   fetchImpl:async(path,opts)=>{
     if(opts.method==="GET")return response(state());
     posts++;local.change("taiwan_art_favs",{});
     return response({},409);
   }});
 assert.equal(result.status,"local_review_required");
 assert.equal(posts,1);
});
test("checkpoint permits additive save when local records remain intact",async()=>{
 const local=storage();
 const result=await run({storage:local,checkpoint:{favs:{a:fav},visited:{}},
   fetchImpl:async(path,opts)=>response(opts.method==="GET"?state():
     state(1,{a:item(fav)}))});
 assert.equal(result.status,"saved");
});

test("after 409, additive retry preserves unrelated server registration and both local categories",async()=>{
 const local=storage({a:fav},{visit:{date:"2026-11-23T00:00:00.000Z",title:"Visited"}});
 let gets=0,posts=0;
 const remote=state(1,{remote:item({title:"Other"})});
 const saved=state(2,{remote:item({title:"Other"}),a:item(fav,2)},
   {visit:item({date:"2026-11-23T00:00:00.000Z",title:"Visited"},2)});
 const result=await run({storage:local,fetchImpl:async(path,opts)=>{
   if(opts.method==="GET")return response(++gets===1?state():remote);
   posts++;
   if(posts===1)return response({error:"stale_revision"},409);
   const payload=JSON.parse(opts.body);
   assert.equal(payload.base_revision,1);
   assert.deepEqual(Object.keys(payload.changes.favs),["a"]);
   assert.deepEqual(Object.keys(payload.changes.visited),["visit"]);
   assert.equal(Object.hasOwn(payload.changes.favs,"remote"),false);
   return response(saved);
 }});
 assert.equal(result.status,"saved");
 assert.equal(result.retried,true);
 assert.equal(posts,2);
 assert.deepEqual(result.preservedRemote.map(x=>x.key),["remote"]);
});
test("after 409, a tombstone conflict blocks all unrelated additive POSTs until review",async()=>{
 const local=storage({conflict:fav,safe:fav});
 let gets=0,posts=0;
 const result=await run({storage:local,fetchImpl:async(path,opts)=>{
   if(opts.method==="GET")return response(++gets===1?state():
     state(1,{conflict:item(null,1,true)}));
   posts++;
   return response({error:"stale_revision"},409);
 }});
 assert.equal(result.status,"needs_review");
 assert.deepEqual(result.review.map(x=>x.key),["conflict"]);
 assert.equal(posts,1);
 assert.deepEqual(JSON.parse(local.getItem("taiwan_art_favs")),
   {conflict:fav,safe:fav});
});

test("cached old tab overwrites local map after POST; server-authoritative save survives",async()=>{
 const local=storage({a:fav});
 let authoritative=state();
 let posts=0;
 const result=await run({storage:local,fetchImpl:async(path,opts)=>{
  if(opts.method==="GET")return response(authoritative);
  posts++;
  const request=JSON.parse(opts.body);
  assert.equal(request.base_revision,0);
  authoritative=state(1,{a:item(fav,1)});
  // Simulate an old tab bypassing Web Locks and replacing the entire map.
  local.change("taiwan_art_favs",{old:{title:"Old",museum:"M"}});
  return response(authoritative);
 }});
 assert.equal(result.status,"saved_server_local_changed");
 assert.equal(result.serverSaved,true);
 assert.equal(result.revision,1);
 assert.equal(posts,1);
 assert.equal(authoritative.favs.a.value.title,"A");
 assert.equal(JSON.parse(local.getItem("taiwan_art_favs")).a,undefined);
 // This confirms server isolation, NOT preservation of legacy localStorage.
});
test("cached old tab cannot resurrect tombstone through additive retry",async()=>{
 const local=storage({a:fav});
 let posts=0;
 const authoritative=state(2,{a:item(null,2,true)});
 const result=await run({storage:local,fetchImpl:async(path,opts)=>{
  if(opts.method==="POST")posts++;
  return response(authoritative);
 }});
 assert.equal(result.status,"needs_review");
 assert.equal(posts,0);
 assert.equal(authoritative.favs.a.deleted,true);
});
test("old tab writes during server GET; additive retry refuses stale local snapshot",async()=>{
 const local=storage({a:fav});
 let posts=0;
 const result=await run({storage:local,fetchImpl:async(path,opts)=>{
  if(opts.method==="GET"){
   local.change("taiwan_art_favs",{old:{title:"Old",museum:"M"}});
   return response(state());
  }
  posts++;return response(state(1));
 }});
 assert.equal(result.status,"local_changed");
 assert.equal(posts,0);
});
test("old tab writes during server GET and checkpoint detects lost exhibition",async()=>{
 const local=storage({a:fav});
 let posts=0;
 const result=await run({storage:local,checkpoint:{favs:{a:fav},visited:{}},
  fetchImpl:async(path,opts)=>{
   if(opts.method==="GET"){
    local.change("taiwan_art_favs",{old:{title:"Old",museum:"M"}});
    return response(state());
   }
   posts++;return response(state(1));
  }});
 assert.equal(result.status,"local_review_required");
 assert.equal(posts,0);
});

test("confirmed POST with checkpoint loss reports server saved but local review required",async()=>{
 const local=storage({a:fav});
 let posts=0;
 const result=await run({storage:local,checkpoint:{favs:{a:fav},visited:{}},
  fetchImpl:async(path,opts)=>{
   if(opts.method==="GET")return response(state());
   posts++;
   local.change("taiwan_art_favs",{old:{title:"Old",museum:"M"}});
   return response(state(1,{a:item(fav)}));
  }});
 assert.equal(result.status,"saved_server_local_review_required");
 assert.equal(result.serverSaved,true);
 assert.equal(result.revision,1);
 assert.equal(result.missing[0].key,"a");
 assert.equal(posts,1);
});
test("confirmed POST with unreadable local snapshot never reports fully saved",async()=>{
 const local=storage({a:fav});
 let posts=0;
 const result=await run({storage:local,fetchImpl:async(path,opts)=>{
  if(opts.method==="GET")return response(state());
  posts++;
  local.change("taiwan_art_favs",["unexpected","array"]);
  return response(state(1,{a:item(fav)}));
 }});
 assert.equal(result.status,"saved_server_local_changed");
 assert.equal(result.serverSaved,true);
 assert.equal(posts,1);
});
