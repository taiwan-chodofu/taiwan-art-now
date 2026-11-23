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
 assert.equal(result.displayResult.status,"saved_server_verified_local_changed");
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
 assert.equal(result.displayResult.status,"saved_server_local_changed");
 assert.equal(posts,1);
});

test("missing trusted checkpoint remains a review even if saved record is verified",async()=>{
 const local=storage();let gets=0;
 const saved={revision:1,favs:{a:{value:fav,revision:1,deleted:false}},visited:{}};
 const result=await run({storage:local,checkpoint:{favs:{a:fav},visited:{}},
  fetchImpl:async(path,options)=>{
   if(options.method==="GET"){gets++;return response(gets===1?
    {revision:0,favs:{},visited:{}}:saved);}
   local.change("taiwan_art_favs",{old:{title:"Old",museum:"M"}});
   return response(saved);
  }});
 assert.equal(result.result.status,"saved_server_local_review_required");
 assert.equal(result.verification.status,"confirmed_on_server");
 assert.equal(result.displayResult.status,"saved_server_local_review_required");
});

test("verified server save renders polite success instead of a warning",async()=>{
 const local=storage();let gets=0,posts=0;
 const saved={revision:1,favs:{a:{value:fav,revision:1,deleted:false}},visited:{}};
 class Node{
  constructor(tag){this.tag=tag;this.attributes={};this.children=[];this.textContent="";}
  setAttribute(k,v){this.attributes[k]=v;}
  appendChild(node){this.children.push(node);}
  replaceChildren(...nodes){this.children=nodes;}
 }
 const doc={createElement:tag=>new Node(tag)},container=new Node("div");
 const output=await run({storage:local,document:doc,container,
  fetchImpl:async(path,opts)=>{
   if(opts.method==="GET"){gets++;return response(gets===1?
    {revision:0,favs:{},visited:{}}:saved);}
   posts++;local.change("taiwan_art_favs",{old:{title:"Old",museum:"M"}});
   return response(saved);
  }});
 assert.equal(output.result.status,"saved_server_local_changed");
 assert.equal(output.verification.status,"confirmed_on_server");
 assert.equal(output.displayed.status,"rendered");
 assert.equal(output.displayed.requiresReview,false);
 assert.equal(container.children[0].attributes.role,"status");
 assert.match(container.children[0].children[0].textContent,/成功儲存/);
 assert.equal(posts,1);
});

test("server record deleted after save never receives calm verified-success copy",async()=>{
 const local=storage();let gets=0,posts=0;
 const saved={revision:1,favs:{a:{value:fav,revision:1,deleted:false}},visited:{}};
 const deleted={revision:2,favs:{a:{value:null,revision:2,deleted:true}},visited:{}};
 const output=await run({storage:local,fetchImpl:async(path,options)=>{
  if(options.method==="GET"){gets++;return response(gets===1?
   {revision:0,favs:{},visited:{}}:deleted);}
  posts++;local.change("taiwan_art_favs",{old:{title:"Old",museum:"M"}});
  return response(saved);
 }});
 assert.equal(output.result.serverSaved,true);
 assert.equal(output.verification.status,"server_records_need_review");
 assert.equal(output.verification.unresolved[0].reason,"deleted_on_server");
 assert.equal(output.displayResult.status,"saved_server_record_deleted");
 assert.equal(posts,1);
 assert.equal(gets,2);
});

test("changed server value gives specific explanation rather than generic warning",async()=>{
 const local=storage();let gets=0;
 const saved={revision:1,favs:{a:{value:fav,revision:1,deleted:false}},visited:{}};
 const changed={revision:2,favs:{a:{value:{...fav,title:"Updated"},revision:2,deleted:false}},visited:{}};
 const output=await run({storage:local,fetchImpl:async(path,options)=>{
  if(options.method==="GET"){gets++;return response(gets===1?
   {revision:0,favs:{},visited:{}}:changed);}
  local.change("taiwan_art_favs",{old:{title:"Old",museum:"M"}});
  return response(saved);
 }});
 assert.equal(output.verification.unresolved[0].reason,"different_server_value");
 assert.equal(output.displayResult.status,"saved_server_record_different");
});
