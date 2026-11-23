const test = require("node:test");
const assert = require("node:assert/strict");
const { remove, LOCK_NAME } = require("../static/js/draft_coordinated_local_removal.js");
const { read } = require("../static/js/draft_legacy_snapshot.js");
const fav = { title: "A", museum: "M", dates: "", url: "" };
const state = { revision: 4, favs: { a: { deleted: true, revision: 3, value: null } }, visited: {} };
function fixture() {
  const data = { taiwan_art_favs: JSON.stringify({ a: fav, b: { ...fav, title: "B" } }),
    taiwan_art_visited: "{}" };
  const writes = [];
  const storage = { getItem: key => data[key] ?? null,
    setItem(key, value) { writes.push([key, value]); data[key] = value; } };
  const locks = { request: async (name, opts, fn) => {
    assert.equal(name, LOCK_NAME); assert.equal(opts.mode, "exclusive");
    return await fn();
  }};
  return { data, writes, storage, locks, reviewedSnapshot: read(storage).snapshot,
    decision: { kind: "favs", key: "a", choice: "remove_from_list" },
    serverState: state, expectedServerRevision: 4,
    fetchFreshState: async () => state };
}
test("explicit removal under cooperative lock preserves other exhibitions", async () => {
  const x = fixture();
  assert.equal((await remove(x)).status, "removed_under_cooperative_lock");
  assert.deepEqual(Object.keys(JSON.parse(x.data.taiwan_art_favs)), ["b"]);
  assert.equal(x.writes.length, 1);
});
test("without Web Locks no write is allowed", async () => {
  const x = fixture(); x.locks = null;
  assert.equal((await remove(x)).status, "not_authorized");
  assert.equal(x.writes.length, 0);
});
test("defer never writes", async () => {
  const x = fixture(); x.decision.choice = "decide_later";
  assert.equal((await remove(x)).status, "not_authorized");
  assert.equal(x.writes.length, 0);
});
test("server revision change blocks deletion", async () => {
  const x = fixture();
  x.fetchFreshState = async () => ({ ...state, revision: 5 });
  assert.equal((await remove(x)).status, "stale_server");
  assert.equal(x.writes.length, 0);
});
test("tombstone replaced blocks deletion", async () => {
  const x = fixture();
  x.fetchFreshState = async () => ({ ...state, favs: {
    a: { deleted: false, revision: 4, value: fav } } });
  assert.equal((await remove(x)).status, "stale_server");
  assert.equal(x.writes.length, 0);
});
test("local change before acquiring lock blocks deletion", async () => {
  const x = fixture();
  x.data.taiwan_art_favs = JSON.stringify({ a: { ...fav, title: "New" }, b: fav });
  assert.equal((await remove(x)).status, "stale_local");
  assert.equal(x.writes.length, 0);
});
test("another cooperative tab updates first; second refuses stale snapshot", async () => {
  const x = fixture();
  const pending = [];
  let tail = Promise.resolve();
  x.locks.request = (_name, _opts, fn) => {
    const p = tail.then(fn); tail = p.catch(() => {}); pending.push(p); return p;
  };
  const first = remove(x);
  const second = remove(x);
  assert.equal((await first).status, "removed_under_cooperative_lock");
  assert.equal((await second).status, "stale_local");
  assert.equal(x.writes.length, 1);
});
test("lock API rejection leaves storage unchanged", async () => {
  const x = fixture(); x.locks.request = async () => { throw Error("unsupported"); };
  assert.equal((await remove(x)).status, "unavailable");
  assert.equal(x.writes.length, 0);
});
test("server read failure leaves storage unchanged", async () => {
  const x = fixture(); x.fetchFreshState = async () => { throw Error("offline"); };
  assert.equal((await remove(x)).status, "unavailable");
  assert.equal(x.writes.length, 0);
});
test("visited removal is isolated", async () => {
  const x = fixture();
  x.data.taiwan_art_visited = JSON.stringify({ v: "2026-11-22T00:00:00Z" });
  x.reviewedSnapshot = read(x.storage).snapshot;
  x.decision = { kind: "visited", key: "v", choice: "remove_from_list" };
  x.serverState = { revision: 4, favs: {}, visited: {
    v: { deleted: true, revision: 3, value: null } } };
  x.fetchFreshState = async () => x.serverState;
  assert.equal((await remove(x)).status, "removed_under_cooperative_lock");
  assert.ok(JSON.parse(x.data.taiwan_art_favs).a);
  assert.equal(JSON.parse(x.data.taiwan_art_visited).v, undefined);
});

test("silently ignored storage write cannot be reported as successful removal", async () => {
  const x = fixture();
  x.storage.setItem = () => {};
  assert.equal((await remove(x)).status, "uncertain_write");
  assert.ok(JSON.parse(x.data.taiwan_art_favs).a);
});
test("unexpected modification to another exhibition during write is detected", async () => {
  const x = fixture();
  x.storage.setItem = (key, value) => {
    const next = JSON.parse(value);
    next.b = { ...fav, title: "Unexpected change" };
    x.data[key] = JSON.stringify(next);
  };
  assert.equal((await remove(x)).status, "uncertain_write");
  assert.ok(JSON.parse(x.data.taiwan_art_favs).b);
});
test("unexpected modification to visited records during removal is detected", async () => {
  const x = fixture();
  x.storage.setItem = (key, value) => {
    x.data[key] = value;
    x.data.taiwan_art_visited = JSON.stringify({ other: "2026-11-23" });
  };
  assert.equal((await remove(x)).status, "uncertain_write");
});
