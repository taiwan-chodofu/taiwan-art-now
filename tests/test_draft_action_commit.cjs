const test = require("node:test");
const assert = require("node:assert/strict");
const { create } = require("../static/js/draft_action_commit.js");
const fav = { title: "A", museum: "M" };
function setup() {
  const data = { taiwan_art_favs: "{}", taiwan_art_visited: "{}" };
  const storage = { getItem: k => data[k] ?? null, setItem: (k,v) => { data[k] = v; } };
  let tail = Promise.resolve();
  const locks = { request: (_name, _opts, fn) => {
    const p = tail.then(fn); tail = p.catch(() => {}); return p;
  }};
  const committed = [], failures = [], busy = [];
  const adapter = create({ storage, locks, onCommitted: x => committed.push(x),
    onFailure: x => failures.push(x), onBusy: (state) => busy.push(state) });
  return { data, storage, locks, committed, failures, busy, adapter };
}
test("success refreshes only after local persistence", async () => {
  const x = setup();
  const result = await x.adapter.commit({ kind: "favs", key: "a", action: "set", value: fav });
  assert.equal(result.status, "written_under_cooperative_lock");
  assert.equal(x.committed.length, 1);
  assert.deepEqual(x.committed[0].value, fav);
  assert.equal(JSON.parse(x.data.taiwan_art_favs).a.title, "A");
  assert.deepEqual(x.busy, [true, false]);
});
test("failed storage write never triggers committed callback", async () => {
  const x = setup();
  x.storage.setItem = () => { throw Error("quota"); };
  assert.equal((await x.adapter.commit({ kind: "favs", key: "a", action: "set", value: fav })).status, "unavailable");
  assert.equal(x.committed.length, 0);
  assert.equal(x.failures.length, 1);
});
test("unavailable lock never changes UI", async () => {
  const x = setup();
  x.locks.request = () => Promise.reject(Error("blocked"));
  await x.adapter.commit({ kind: "favs", key: "a", action: "set", value: fav });
  assert.equal(x.committed.length, 0);
  assert.equal(x.failures.length, 1);
});
test("concurrent duplicate click does not enqueue second mutation", async () => {
  const x = setup();
  const first = x.adapter.commit({ kind: "favs", key: "a", action: "set", value: fav });
  const second = await x.adapter.commit({ kind: "favs", key: "a", action: "remove" });
  assert.equal(second.status, "busy");
  assert.equal((await first).status, "written_under_cooperative_lock");
  assert.equal(x.committed.length, 1);
  assert.ok(JSON.parse(x.data.taiwan_art_favs).a);
});
test("remove callback follows persisted deletion", async () => {
  const x = setup();
  await x.adapter.commit({ kind: "favs", key: "a", action: "set", value: fav });
  const result = await x.adapter.commit({ kind: "favs", key: "a", action: "remove" });
  assert.equal(result.status, "written_under_cooperative_lock");
  assert.equal(x.committed[1].action, "remove");
  assert.equal(JSON.parse(x.data.taiwan_art_favs).a, undefined);
});
test("invalid value cannot trigger success UI", async () => {
  const x = setup();
  const result = await x.adapter.commit({ kind: "visited", key: "a", action: "set", value: {} });
  assert.equal(result.status, "unavailable");
  assert.equal(x.committed.length, 0);
});

test("UI callback exception does not pretend storage failed", async () => {
  const x = setup();
  const adapter = create({ storage: x.storage, locks: x.locks,
    onCommitted: () => { throw Error("render"); },
    onFailure: () => { throw Error("should not run"); } });
  const result = await adapter.commit({ kind: "favs", key: "a", action: "set", value: fav });
  assert.equal(result.status, "committed_callback_failed");
  assert.equal(JSON.parse(x.data.taiwan_art_favs).a.title, "A");
});

test("busy-start callback exception releases pending slot without writing", async () => {
  const x=setup();
  let count=0;
  const adapter=create({storage:x.storage,locks:x.locks,
    onCommitted:v=>x.committed.push(v),onFailure:v=>x.failures.push(v),
    onBusy:busy=>{if(busy&&count++===0)throw Error("UI unavailable");}});
  const first=await adapter.commit({kind:"favs",key:"a",action:"set",value:fav});
  assert.equal(first.status,"unavailable");
  assert.equal(x.committed.length,0);
  assert.deepEqual(JSON.parse(x.data.taiwan_art_favs),{});
  const second=await adapter.commit({kind:"favs",key:"a",action:"set",value:fav});
  assert.equal(second.status,"written_under_cooperative_lock");
  assert.equal(x.committed.length,1);
});
test("busy-end callback exception cannot turn persisted success into failure", async () => {
  const x=setup();
  const adapter=create({storage:x.storage,locks:x.locks,
    onCommitted:v=>x.committed.push(v),onFailure:v=>x.failures.push(v),
    onBusy:busy=>{if(!busy)throw Error("UI end");}});
  const first=await adapter.commit({kind:"favs",key:"a",action:"set",value:fav});
  assert.equal(first.status,"written_under_cooperative_lock");
  assert.equal(x.failures.length,0);
  const second=await adapter.commit({kind:"favs",key:"a",action:"remove"});
  assert.equal(second.status,"written_under_cooperative_lock");
  assert.equal(x.committed.length,2);
});
