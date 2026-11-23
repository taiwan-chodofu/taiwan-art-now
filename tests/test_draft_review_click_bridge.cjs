const test = require("node:test");
const assert = require("node:assert/strict");
const { mount } = require("../static/js/draft_review_click_bridge.js");
const { read } = require("../static/js/draft_legacy_snapshot.js");
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.value = ""; this.events = {}; this.textContent = ""; this.attributes = {}; }
  setAttribute(name, value) { this.attributes[name] = value; }
  appendChild(child) { this.children.push(child); return child; }
  addEventListener(name, fn) { this.events[name] = fn; }
  remove() { this.removed = true; }
}
const doc = { createElement: tag => new Element(tag) };
const fav = { title: "A", museum: "M", dates: "", url: "" };
const serverState = { revision: 3, favs: { a: { value: null, deleted: true, revision: 2 } }, visited: {} };
const report = { status: "needs_review", review: [{ kind: "favs", key: "a", reason: "explicit_deletion_conflict" }] };
const elements = (root, tag) => [root, ...root.children.flatMap(x => elements(x, tag))].filter(x => x.tag === tag);
function setup() {
  const data = { taiwan_art_favs: JSON.stringify({ a: fav }), taiwan_art_visited: "{}" };
  const storage = { getItem: key => data[key] };
  const calls = [];
  const request = async (url, payload) => {
    calls.push([url, payload]);
    return calls.length % 2 ? { token: "synthetic" } : { revision: 4 };
  };
  const container = new Element("main");
  const instance = mount({ container, report, doc, serverState, storage,
    localSnapshot: read(storage).snapshot, request });
  return { container, instance, calls, data };
}
test("rendering and default defer never sends a request", async () => {
  const x = setup();
  assert.equal(x.calls.length, 0);
  await x.instance.submit();
  assert.equal(x.calls.length, 0);
});
test("selection change alone never sends a request", () => {
  const x = setup();
  const select = elements(x.container, "select")[0];
  select.value = "keep_saved"; select.events.change();
  assert.equal(x.calls.length, 0);
});
test("explicit click triggers issue then consume", async () => {
  const x = setup();
  const select = elements(x.container, "select")[0];
  select.value = "keep_saved"; select.events.change();
  await elements(x.container, "button")[0].events.click();
  assert.equal(x.calls.length, 2);
  assert.match(x.calls[0][0], /issue$/);
  assert.match(x.calls[1][0], /consume$/);
});
test("remove never sends requests", async () => {
  const x = setup();
  const select = elements(x.container, "select")[0];
  select.value = "remove_from_list"; select.events.change();
  await x.instance.submit();
  assert.equal(x.calls.length, 0);
});
test("changed local snapshot blocks confirmation", async () => {
  const x = setup();
  const select = elements(x.container, "select")[0];
  select.value = "keep_saved"; select.events.change();
  x.data.taiwan_art_favs = "{}";
  await x.instance.submit();
  assert.equal(x.calls.length, 0);
});
test("disposed review blocks click submission", async () => {
  const x = setup();
  x.instance.dispose();
  await x.instance.submit();
  assert.equal(x.calls.length, 0);
});
test("ordinary merge creates no button", () => {
  const data = { taiwan_art_favs: "{}", taiwan_art_visited: "{}" };
  const storage = { getItem: key => data[key] };
  const container = new Element("main");
  const instance = mount({ container, doc, storage, serverState,
    localSnapshot: read(storage).snapshot,
    report: { status: "prepared", review: [] },
    request: async () => { throw Error("unexpected"); } });
  assert.equal(instance.rendered, false);
  assert.equal(container.children.length, 0);
});

test("successful review confirmation cannot be submitted twice with a stale revision", async () => {
  const x = setup();
  const select = elements(x.container, "select")[0];
  select.value = "keep_saved"; select.events.change();
  const button = elements(x.container, "button")[0];
  await button.events.click();
  assert.equal(x.calls.length, 2);
  assert.equal(button.disabled, true);
  await button.events.click();
  await x.instance.submit();
  assert.equal(x.calls.length, 2);
});

test("ambiguous consume network failure locks review and prevents duplicate confirmation", async () => {
  const data = { taiwan_art_favs: JSON.stringify({ a: fav }), taiwan_art_visited: "{}" };
  const storage = { getItem: key => data[key] };
  const calls = [];
  const container = new Element("main");
  const instance = mount({ container, report, doc, serverState, storage,
    localSnapshot: read(storage).snapshot,
    request: async (url) => {
      calls.push(url);
      if (url.endsWith("/issue")) return { token: "synthetic" };
      throw Error("response lost after server may have committed");
    } });
  const select = elements(container, "select")[0];
  select.value = "keep_saved"; select.events.change();
  const button = elements(container, "button")[0];
  await button.events.click();
  assert.equal(calls.length, 2);
  assert.equal(button.disabled, true);
  assert.match(elements(container, "p").map(x => x.textContent).join(" "), /登録状況をもう一度確認/);
  await button.events.click();
  await instance.submit();
  assert.equal(calls.length, 2);
});
test("failed token issue does not allow stale review to be resubmitted", async () => {
  const data = { taiwan_art_favs: JSON.stringify({ a: fav }), taiwan_art_visited: "{}" };
  const storage = { getItem: key => data[key] };
  let calls = 0;
  const container = new Element("main");
  const instance = mount({ container, report, doc, serverState, storage,
    localSnapshot: read(storage).snapshot,
    request: async () => { calls++; return {}; } });
  const select = elements(container, "select")[0];
  select.value = "keep_saved"; select.events.change();
  await instance.submit();
  await instance.submit();
  assert.equal(calls, 1);
  assert.equal(elements(container, "button")[0].disabled, true);
});

test("server check appears only after confirmation attempt and never posts", async () => {
  const data={taiwan_art_favs:JSON.stringify({a:fav}),taiwan_art_visited:"{}"};
  const storage={getItem:key=>data[key]};
  const container=new Element("main");
  let gets=0,requests=0;
  const instance=mount({container,report,doc,serverState,storage,
    localSnapshot:read(storage).snapshot,
    request:async url=>{requests++;if(url.endsWith("/issue"))return {token:"synthetic"};throw Error("lost response");},
    fetchImpl:async(path,opts)=>{
      gets++;assert.equal(opts.method,"GET");
      assert.equal(path,"/api/private-subscribers/v2/state");
      return {status:200,ok:true,headers:{get:k=>k==="content-type"?"application/json":"no-store"},
        json:async()=>({revision:4,favs:{a:{value:fav,deleted:false,revision:4}},visited:{}})};
    }});
  const buttons=elements(container,"button");
  assert.equal(buttons.length,3);
  assert.equal(buttons[2].disabled,true);
  await instance.inspect();
  assert.equal(gets,0);
  const select=elements(container,"select")[0];
  select.value="keep_saved";select.events.change();
  await instance.submit();
  assert.equal(requests,2);
  assert.equal(buttons[0].disabled,true);
  assert.equal(buttons[2].disabled,false);
  await buttons[2].events.click();
  assert.equal(gets,1);
  assert.equal(requests,2);
  assert.match(elements(container,"p").map(x=>x.textContent).join(" "),/この展示は登録されています/);
});

test("concurrent status checks issue only one GET and allow later manual recheck", async () => {
 const data={taiwan_art_favs:JSON.stringify({a:fav}),taiwan_art_visited:"{}"};
 const storage={getItem:key=>data[key]};
 const container=new Element("main");
 let resolveGet,gets=0;
 const instance=mount({container,report,doc,serverState,storage,
   localSnapshot:read(storage).snapshot,
   request:async url=>url.endsWith("/issue")?{token:"synthetic"}:Promise.reject(Error("lost")),
   fetchImpl:async()=>{gets++;return new Promise(resolve=>{resolveGet=resolve;});}});
 const select=elements(container,"select")[0];select.value="keep_saved";select.events.change();
 await instance.submit();
 const first=instance.inspect(),second=instance.inspect();
 assert.equal(gets,1);
 resolveGet({status:200,ok:true,headers:{get:k=>k==="content-type"?"application/json":"no-store"},
   json:async()=>({revision:4,favs:{a:{value:fav,deleted:false,revision:4}},visited:{}})});
 await Promise.all([first,second]);
 assert.equal(elements(container,"button").find(x=>x.textContent==="登録状況をもう一度確認").disabled,false);
 const third=instance.inspect();
 assert.equal(gets,2);
 resolveGet({status:200,ok:true,headers:{get:k=>k==="content-type"?"application/json":"no-store"},
   json:async()=>({revision:4,favs:{a:{value:fav,deleted:false,revision:4}},visited:{}})});
 await third;
});
test("late status response after review disposal does not update removed status", async () => {
 const data={taiwan_art_favs:JSON.stringify({a:fav}),taiwan_art_visited:"{}"};
 const storage={getItem:key=>data[key]};
 const container=new Element("main");
 let resolveGet;
 const instance=mount({container,report,doc,serverState,storage,
   localSnapshot:read(storage).snapshot,
   request:async url=>url.endsWith("/issue")?{token:"synthetic"}:Promise.reject(Error("lost")),
   fetchImpl:async()=>new Promise(resolve=>{resolveGet=resolve;})});
 const select=elements(container,"select")[0];select.value="keep_saved";select.events.change();
 await instance.submit();
 const status=elements(container,"p").at(-1);
 const before=status.textContent;
 const pending=instance.inspect();
 instance.dispose();
 resolveGet({status:200,ok:true,headers:{get:k=>k==="content-type"?"application/json":"no-store"},
   json:async()=>({revision:4,favs:{a:{value:fav,deleted:false,revision:4}},visited:{}})});
 await pending;
 assert.equal(status.textContent,before);
 assert.equal(status.removed,true);
});

test("server inspection stays disabled while confirmation is in flight", async () => {
 const data={taiwan_art_favs:JSON.stringify({a:fav}),taiwan_art_visited:"{}"};
 const storage={getItem:key=>data[key]};
 const container=new Element("main");
 let resolveConsume,gets=0;
 const instance=mount({container,report,doc,serverState,storage,
  localSnapshot:read(storage).snapshot,
  request:async url=>url.endsWith("/issue")?{token:"synthetic"}:
   new Promise(resolve=>{resolveConsume=resolve;}),
  fetchImpl:async()=>{gets++;throw Error("should not inspect yet");}});
 const select=elements(container,"select")[0];select.value="keep_saved";select.events.change();
 const pending=instance.submit();
 await Promise.resolve();await Promise.resolve();await Promise.resolve();
 assert.equal(elements(container,"button").find(x=>x.textContent==="登録状況をもう一度確認").disabled,true);
 await instance.inspect();
 assert.equal(gets,0);
 resolveConsume({revision:4});
 await pending;
 assert.equal(elements(container,"button").find(x=>x.textContent==="登録状況をもう一度確認").disabled,false);
});
test("missing server record is explicitly distinguished from a confirmed save", async () => {
 const data={taiwan_art_favs:JSON.stringify({a:fav}),taiwan_art_visited:"{}"};
 const storage={getItem:key=>data[key]};
 const container=new Element("main");
 const instance=mount({container,report,doc,serverState,storage,
  localSnapshot:read(storage).snapshot,
  request:async url=>url.endsWith("/issue")?{token:"synthetic"}:Promise.reject(Error("lost")),
  fetchImpl:async()=>({status:200,ok:true,
   headers:{get:k=>k==="content-type"?"application/json":"no-store"},
   json:async()=>({revision:4,favs:{},visited:{}})})});
 const select=elements(container,"select")[0];select.value="keep_saved";select.events.change();
 await instance.submit();await instance.inspect();
 const words=elements(container,"p").map(x=>x.textContent).join(" ");
 assert.match(words,/登録は確認できませんでした/);
 assert.doesNotMatch(words,/この展示は登録されています/);
});

test("review recheck button uses plain Japanese without requiring a page reload", () => {
 const x=setup();
 assert.equal(elements(x.container,"button")[0].textContent,"選択した展示を確認");
 const data={taiwan_art_favs:JSON.stringify({a:fav}),taiwan_art_visited:"{}"};
 const storage={getItem:key=>data[key]};
 const container=new Element("main");
 mount({container,report,doc,serverState,storage,
   localSnapshot:read(storage).snapshot,request:async()=>({}),
   fetchImpl:async()=>{throw Error("not called until user requests inspection");}});
 assert.equal(elements(container,"button").find(x=>x.textContent==="登録状況をもう一度確認").textContent,"登録状況をもう一度確認");
 assert.equal(elements(container,"button").find(x=>x.textContent==="登録状況をもう一度確認").disabled,true);
});

test("successful confirmation reports remaining conflicting exhibitions without writing them",async()=>{
 const data={taiwan_art_favs:JSON.stringify({a:fav,b:fav}),taiwan_art_visited:"{}"};
 const storage={getItem:key=>data[key]};
 const multiReport={status:"needs_review",review:[
   {kind:"favs",key:"a",reason:"explicit_deletion_conflict"},
   {kind:"favs",key:"b",reason:"explicit_deletion_conflict"}]};
 const multiState={revision:3,favs:{
   a:{value:null,deleted:true,revision:2},
   b:{value:null,deleted:true,revision:2}},visited:{}};
 const calls=[];
 const container=new Element("main");
 const instance=mount({container,report:multiReport,doc,serverState:multiState,
   storage,localSnapshot:read(storage).snapshot,
   request:async(url)=>{calls.push(url);return url.endsWith("/issue")?{token:"synthetic"}:{revision:4};}});
 const selects=elements(container,"select");
 selects[0].value="keep_saved";selects[0].events.change();
 await instance.submit();
 assert.equal(calls.length,2);
 assert.match(elements(container,"p").map(x=>x.textContent).join(" "),/あと1件、確認が必要な展示があります/);
 await instance.submit();
 assert.equal(calls.length,2);
});
test("choosing remove does not misleadingly claim removal succeeded",async()=>{
 const x=setup();
 const select=elements(x.container,"select")[0];
 select.value="remove_from_list";select.events.change();
 await x.instance.submit();
 assert.equal(x.calls.length,0);
 assert.match(elements(x.container,"p").map(x=>x.textContent).join(" "),/まだ反映されていません/);
});

test("confirmed save automatically refreshes and lists only remaining tombstone conflicts",async()=>{
 const data={taiwan_art_favs:JSON.stringify({a:fav,b:fav,c:fav}),taiwan_art_visited:"{}"};
 const storage={getItem:key=>data[key]};
 const report3={status:"needs_review",review:["a","b","c"].map(key=>({
   kind:"favs",key,reason:"explicit_deletion_conflict"}))};
 const server3={revision:3,favs:Object.fromEntries(["a","b","c"].map(key=>
   [key,{value:null,deleted:true,revision:2}])),visited:{}};
 let gets=0,posts=0;
 const container=new Element("main");
 const instance=mount({container,report:report3,doc,serverState:server3,storage,
  localSnapshot:read(storage).snapshot,
  request:async url=>{posts++;return url.endsWith("/issue")?{token:"synthetic"}:{revision:4};},
  fetchImpl:async(path,opts)=>{
   gets++;assert.equal(opts.method,"GET");
   return {ok:true,status:200,headers:{get:k=>k==="content-type"?"application/json":"no-store"},
    json:async()=>({revision:4,favs:{
     a:{value:fav,deleted:false,revision:4},
     b:{value:null,deleted:true,revision:2},
     c:{value:fav,deleted:false,revision:4}},visited:{}})};
  }});
 const select=elements(container,"select")[0];
 select.value="keep_saved";select.events.change();
 await instance.submit();
 assert.equal(gets,1);
 assert.equal(posts,2);
 assert.match(elements(container,"p").map(x=>x.textContent).join(" "),/あと1件、確認が必要/);
 const pending=elements(container,"div").filter(x=>x.attributes?.["aria-label"]==="確認が必要な展示")[0];
 assert.deepEqual(elements(pending,"p").map(x=>x.textContent),["A（観たい）"]);
 const next=elements(container,"button").find(x=>x.textContent==="残りの展示を確認");
 assert.equal(next.disabled,false);
 await next.events.click();
 assert.equal(gets,2);
 assert.equal(posts,2);
 assert.equal(elements(container,"section").filter(x=>!x.removed).length,1);
 assert.equal(elements(container,"select").filter(x=>!x.removed).length>=1,true);
 await instance.submit();
 assert.equal(posts,2);
});

test("next review rechecks latest state and never opens an already resolved conflict",async()=>{
 const data={taiwan_art_favs:JSON.stringify({a:fav,b:fav}),taiwan_art_visited:"{}"};
 const storage={getItem:key=>data[key]};
 const report2={status:"needs_review",review:["a","b"].map(key=>({kind:"favs",key,reason:"explicit_deletion_conflict"}))};
 const state={revision:3,favs:{a:{deleted:true,value:null,revision:2},b:{deleted:true,value:null,revision:2}},visited:{}};
 let gets=0,posts=0;
 const container=new Element("main");
 const instance=mount({container,report:report2,doc,serverState:state,storage,
  localSnapshot:read(storage).snapshot,
  request:async url=>{posts++;return url.endsWith("/issue")?{token:"synthetic"}:{revision:4};},
  fetchImpl:async()=>{gets++;return {ok:true,status:200,headers:{get:k=>k==="content-type"?"application/json":"no-store"},
   json:async()=>({revision:gets===1?4:5,favs:{
    a:{value:fav,deleted:false,revision:4},
    b:gets===1?{value:null,deleted:true,revision:2}:{value:fav,deleted:false,revision:5}},visited:{}})};}});
 const select=elements(container,"select")[0];select.value="keep_saved";select.events.change();
 await instance.submit();
 const next=elements(container,"button").find(x=>x.textContent==="残りの展示を確認");
 assert.equal(next.disabled,false);
 await next.events.click();
 assert.equal(gets,2);
 assert.equal(posts,2);
 assert.match(elements(container,"p").map(x=>x.textContent).join(" "),/確認が必要な展示はありません/);
});

test("double-clicking next review performs only one fresh GET",async()=>{
 const data={taiwan_art_favs:JSON.stringify({a:fav,b:fav}),taiwan_art_visited:"{}"};
 const storage={getItem:key=>data[key]};
 const report2={status:"needs_review",review:["a","b"].map(key=>({kind:"favs",key,reason:"explicit_deletion_conflict"}))};
 const state={revision:3,favs:{a:{deleted:true,value:null,revision:2},b:{deleted:true,value:null,revision:2}},visited:{}};
 let gets=0,resolveNext,posts=0;
 const response=revision=>({ok:true,status:200,headers:{get:k=>k==="content-type"?"application/json":"no-store"},
  json:async()=>({revision,favs:{a:{deleted:false,value:fav,revision:4},b:{deleted:true,value:null,revision:2}},visited:{}})});
 const container=new Element("main");
 const instance=mount({container,report:report2,doc,serverState:state,storage,localSnapshot:read(storage).snapshot,
  request:async url=>{posts++;return url.endsWith("/issue")?{token:"synthetic"}:{revision:4};},
  fetchImpl:async()=>{gets++;return gets===1?response(4):new Promise(resolve=>{resolveNext=resolve;});}});
 const select=elements(container,"select")[0];select.value="keep_saved";select.events.change();
 await instance.submit();
 const next=elements(container,"button").find(x=>x.textContent==="残りの展示を確認");
 const first=next.events.click(),second=next.events.click();
 assert.equal(gets,2);
 resolveNext(response(4));
 await Promise.all([first,second]);
 assert.equal(posts,2);
});
test("next review GET failure leaves existing review and allows retry",async()=>{
 const data={taiwan_art_favs:JSON.stringify({a:fav,b:fav}),taiwan_art_visited:"{}"};
 const storage={getItem:key=>data[key]};
 const report2={status:"needs_review",review:["a","b"].map(key=>({kind:"favs",key,reason:"explicit_deletion_conflict"}))};
 const state={revision:3,favs:{a:{deleted:true,value:null,revision:2},b:{deleted:true,value:null,revision:2}},visited:{}};
 let gets=0,posts=0;
 const container=new Element("main");
 const instance=mount({container,report:report2,doc,serverState:state,storage,localSnapshot:read(storage).snapshot,
  request:async url=>{posts++;return url.endsWith("/issue")?{token:"synthetic"}:{revision:4};},
  fetchImpl:async()=>{gets++;if(gets===2)throw Error("offline");return {ok:true,status:200,
   headers:{get:k=>k==="content-type"?"application/json":"no-store"},
   json:async()=>({revision:4,favs:{a:{deleted:false,value:fav,revision:4},b:{deleted:true,value:null,revision:2}},visited:{}})};}});
 const select=elements(container,"select")[0];select.value="keep_saved";select.events.change();
 await instance.submit();
 const next=elements(container,"button").find(x=>x.textContent==="残りの展示を確認");
 await next.events.click();
 assert.equal(next.disabled,false);
 assert.match(elements(container,"p").map(x=>x.textContent).join(" "),/もう一度お試しください/);
 assert.equal(posts,2);
 await next.events.click();
 assert.equal(gets,3);
 assert.equal(posts,2);
});

test("three exhibitions can be confirmed sequentially without stale revisions or extra writes",async()=>{
 const keys=["a","b","c"];
 const data={taiwan_art_favs:JSON.stringify(Object.fromEntries(keys.map(k=>[k,fav]))),taiwan_art_visited:"{}"};
 const storage={getItem:key=>data[key]};
 const report3={status:"needs_review",review:keys.map(key=>({kind:"favs",key,reason:"explicit_deletion_conflict"}))};
 let revision=3,posts=0,gets=0;
 const entries=Object.fromEntries(keys.map(key=>[key,{value:null,deleted:true,revision:2}]));
 const container=new Element("main");
 mount({container,report:report3,doc,serverState:{revision,favs:structuredClone(entries),visited:{}},
  storage,localSnapshot:read(storage).snapshot,
  request:async (url,payload)=>{
   posts++;
   if(url.endsWith("/issue"))return {token:"synthetic"};
   const next=keys.find(k=>entries[k].deleted);
   revision++;
   entries[next]={value:fav,deleted:false,revision};
   return {revision};
  },
  fetchImpl:async()=>{gets++;return {ok:true,status:200,
   headers:{get:k=>k==="content-type"?"application/json":"no-store"},
   json:async()=>({revision,favs:structuredClone(entries),visited:{}})};}});
 for(let i=0;i<3;i++){
  const live=(root,tag)=>root.removed?[]:[...(root.tag===tag?[root]:[]),...root.children.flatMap(child=>live(child,tag))];
  const selects=live(container,"select").filter(x=>x.events.change);
  const current=selects[0];
  current.value="keep_saved";current.events.change();
  const confirm=live(container,"button").find(x=>x.textContent==="選択した展示を確認");
  await confirm.events.click();
  assert.equal(posts,(i+1)*2);
  if(i<2){
   const next=live(container,"button").find(x=>x.textContent==="残りの展示を確認");
   await next.events.click();
   assert.equal(posts,(i+1)*2);
  }
 }
 assert.equal(revision,6);
 assert.equal(keys.every(k=>!entries[k].deleted),true);
 assert.equal(gets,4);
});

test("next review refuses changed local records without sending another write",async()=>{
 const data={taiwan_art_favs:JSON.stringify({a:fav,b:fav}),taiwan_art_visited:"{}"};
 const storage={getItem:key=>data[key]};
 const report2={status:"needs_review",review:["a","b"].map(key=>({kind:"favs",key,reason:"explicit_deletion_conflict"}))};
 const state={revision:3,favs:{a:{deleted:true,value:null,revision:2},b:{deleted:true,value:null,revision:2}},visited:{}};
 let gets=0,posts=0;
 const container=new Element("main");
 mount({container,report:report2,doc,serverState:state,storage,localSnapshot:read(storage).snapshot,
  request:async url=>{posts++;return url.endsWith("/issue")?{token:"synthetic"}:{revision:4};},
  fetchImpl:async()=>{gets++;return {ok:true,status:200,
   headers:{get:k=>k==="content-type"?"application/json":"no-store"},
   json:async()=>({revision:4,favs:{a:{deleted:false,value:fav,revision:4},b:{deleted:true,value:null,revision:2}},visited:{}})};}});
 const select=elements(container,"select")[0];select.value="keep_saved";select.events.change();
 await elements(container,"button").find(x=>x.textContent==="選択した展示を確認").events.click();
 data.taiwan_art_favs=JSON.stringify({a:fav,b:fav,c:fav});
 const next=elements(container,"button").find(x=>x.textContent==="残りの展示を確認");
 await next.events.click();
 assert.equal(gets,2);
 assert.equal(posts,2);
 assert.match(elements(container,"p").map(x=>x.textContent).join(" "),/この端末の記録が変わりました/);
 assert.equal(next.disabled,true);
});

test("review shows the exhibition title instead of an opaque storage key",()=>{
 const x=setup();
 const prompts=elements(x.container,"p").map(node=>node.textContent);
 assert.equal(prompts.some(line=>line.includes("Aを「観たい」リストに残しますか？")),true);
});

test("stale GET after confirmed write never enables next exhibition",async()=>{
 const data={taiwan_art_favs:JSON.stringify({a:fav,b:fav}),taiwan_art_visited:"{}"};
 const storage={getItem:key=>data[key]};
 const report2={status:"needs_review",review:["a","b"].map(key=>({kind:"favs",key,reason:"explicit_deletion_conflict"}))};
 const state={revision:3,favs:{a:{deleted:true,value:null,revision:2},b:{deleted:true,value:null,revision:2}},visited:{}};
 let posts=0;
 const container=new Element("main");
 const instance=mount({container,report:report2,doc,serverState:state,storage,localSnapshot:read(storage).snapshot,
  request:async url=>{posts++;return url.endsWith("/issue")?{token:"synthetic"}:{revision:4};},
  fetchImpl:async()=>({ok:true,status:200,headers:{get:k=>k==="content-type"?"application/json":"no-store"},
   json:async()=>({revision:3,favs:state.favs,visited:{}})})});
 const select=elements(container,"select")[0];select.value="keep_saved";select.events.change();
 await instance.submit();
 const next=elements(container,"button").find(x=>x.textContent==="残りの展示を確認");
 assert.equal(next.disabled,true);
 assert.equal(posts,2);
 assert.match(elements(container,"p").map(x=>x.textContent).join(" "),/登録状況を確認できませんでした/);
});
