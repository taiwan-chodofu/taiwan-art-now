const test=require("node:test");
const assert=require("node:assert/strict");
const {run}=require("../static/js/draft_save_review_flow.js");
const fav={title:"Art",museum:"M",dates:"2026",url:""};
function storage(){
 const data={taiwan_art_favs:JSON.stringify({a:fav}),taiwan_art_visited:"{}"};
 return {getItem:k=>data[k]??null,setItem(){throw Error("unexpected write");},
  change(k,v){data[k]=JSON.stringify(v);}};
}
function response(body,status=200){
 return {status,ok:status>=200&&status<300,
  headers:{get:k=>k==="content-type"?"application/json":k==="cache-control"?"no-store":null},
  json:async()=>body};
}
test("after legacy tab overwrites local map, verify server via GET without retry POST",async()=>{
 const local=storage();let gets=0,posts=0;
 const saved={revision:1,favs:{a:{value:fav,revision:1,deleted:false}},visited:{}};
 const result=await run({storage:local,fetchImpl:async(path,options)=>{
  if(options.method==="GET"){gets++;return response(gets===1?
   {revision:0,favs:{},visited:{}}:saved);}
  posts++;local.change("taiwan_art_favs",{old:{title:"Old",museum:"M"}});
  return response(saved);
 }});
 assert.equal(result.result.status,"saved_server_local_changed");
 assert.equal(result.verification.status,"confirmed_on_server");
 assert.equal(posts,1);
 assert.equal(gets,2);
});
test("read-only check failure does not trigger a second save",async()=>{
 const local=storage();let gets=0,posts=0;
 const saved={revision:1,favs:{a:{value:fav,revision:1,deleted:false}},visited:{}};
 const result=await run({storage:local,fetchImpl:async(path,options)=>{
  if(options.method==="GET"){gets++;if(gets===2)throw Error("offline");
   return response({revision:0,favs:{},visited:{}});}
  posts++;local.change("taiwan_art_favs",{old:{title:"Old",museum:"M"}});
  return response(saved);
 }});
 assert.equal(result.result.serverSaved,true);
 assert.equal(result.verification.status,"could_not_verify");
 assert.equal(posts,1);
});
