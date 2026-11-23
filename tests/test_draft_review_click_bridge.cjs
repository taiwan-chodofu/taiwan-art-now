const test = require("node:test");
const assert = require("node:assert/strict");
const { mount } = require("../static/js/draft_review_click_bridge.js");
const { read } = require("../static/js/draft_legacy_snapshot.js");
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.value = ""; this.events = {}; this.textContent = ""; }
  setAttribute() {}
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
  assert.equal(buttons.length,2);
  assert.equal(buttons[1].disabled,true);
  await instance.inspect();
  assert.equal(gets,0);
  const select=elements(container,"select")[0];
  select.value="keep_saved";select.events.change();
  await instance.submit();
  assert.equal(requests,2);
  assert.equal(buttons[0].disabled,true);
  assert.equal(buttons[1].disabled,false);
  await buttons[1].events.click();
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
 assert.equal(elements(container,"button")[1].disabled,false);
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
 assert.equal(elements(container,"button")[1].disabled,true);
 await instance.inspect();
 assert.equal(gets,0);
 resolveConsume({revision:4});
 await pending;
 assert.equal(elements(container,"button")[1].disabled,false);
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
 assert.equal(elements(container,"button")[1].textContent,"登録状況をもう一度確認");
 assert.equal(elements(container,"button")[1].disabled,true);
});
