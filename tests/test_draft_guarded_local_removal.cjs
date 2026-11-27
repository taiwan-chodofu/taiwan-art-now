const test = require("node:test");
const assert = require("node:assert/strict");
const { remove } = require("../static/js/draft_guarded_local_removal.js");
const { read } = require("../static/js/draft_legacy_snapshot.js");
const fav = { title: "A", museum: "M", dates: "", url: "" };
const remote = { revision: 4, favs: { a: { deleted: true, value: null, revision: 3 } }, visited: {} };
function setup() {
  const data = { taiwan_art_favs: JSON.stringify({ a: fav, b: { ...fav, title: "B" } }),
    taiwan_art_visited: JSON.stringify({ a: "2026-11-22T00:00:00Z" }) };
  const writes = [];
  const storage = { getItem: k => data[k] ?? null, setItem(k, v) { writes.push([k, v]); data[k] = v; } };
  const reviewedSnapshot = read(storage).snapshot;
  const decision = { kind: "favs", key: "a", choice: "remove_from_list" };
  return { storage, data, writes, reviewedSnapshot, decision };
}
function attempt(x, extras = {}) {
  return remove({ storage: x.storage, decision: x.decision,
    reviewedSnapshot: x.reviewedSnapshot, serverState: remote,
    expectedServerRevision: 4, ...extras });
}
test("explicit removal preserves other saved exhibitions and visited", () => {
  const x = setup();
  const result = attempt(x);
  assert.equal(result.status, "removed_locally_non_atomic");
  assert.deepEqual(Object.keys(JSON.parse(x.data.taiwan_art_favs)), ["b"]);
  assert.ok(JSON.parse(x.data.taiwan_art_visited).a);
  assert.equal(x.writes.length, 1);
});
test("defer never writes", () => {
  const x = setup();
  assert.equal(attempt(x, { decision: { ...x.decision, choice: "decide_later" } }).status, "not_authorized");
  assert.equal(x.writes.length, 0);
});
test("keep never writes", () => {
  const x = setup();
  assert.equal(attempt(x, { decision: { ...x.decision, choice: "keep_saved" } }).status, "not_authorized");
  assert.equal(x.writes.length, 0);
});
test("no explicit server tombstone never writes", () => {
  const x = setup();
  assert.equal(attempt(x, { serverState: { ...remote, favs: { a: { deleted: false, revision: 3 } } } }).status, "not_authorized");
  assert.equal(x.writes.length, 0);
});
test("stale server revision never writes", () => {
  const x = setup();
  assert.equal(attempt(x, { expectedServerRevision: 3 }).status, "not_authorized");
  assert.equal(x.writes.length, 0);
});
test("changed local favorite never writes", () => {
  const x = setup();
  x.data.taiwan_art_favs = JSON.stringify({ a: { ...fav, title: "New" }, b: { ...fav, title: "B" } });
  assert.equal(attempt(x).status, "stale_local");
  assert.equal(x.writes.length, 0);
});
test("another item added locally never gets overwritten", () => {
  const x = setup();
  x.data.taiwan_art_favs = JSON.stringify({ ...JSON.parse(x.data.taiwan_art_favs), c: fav });
  assert.equal(attempt(x).status, "stale_local");
  assert.equal(x.writes.length, 0);
});
test("change between snapshot read and raw check aborts", () => {
  const x = setup();
  let count = 0;
  const original = x.storage.getItem;
  x.storage.getItem = key => {
    count++;
    if (count === 4) x.data.taiwan_art_favs = JSON.stringify({ a: fav, b: fav, c: fav });
    return original(key);
  };
  const result = attempt(x);
  assert.ok(["stale_local", "uncertain_write"].includes(result.status));
  assert.equal(x.writes.length, 0);
});
test("storage write failure does not report success", () => {
  const x = setup();
  x.storage.setItem = () => { throw Error("quota"); };
  assert.equal(attempt(x).status, "storage_unavailable");
});
test("visited removal does not touch favorites", () => {
  const x = setup();
  const visitedRemote = { revision: 4, favs: {}, visited: {
    a: { deleted: true, value: null, revision: 3 } } };
  const result = attempt(x, { decision: { kind: "visited", key: "a", choice: "remove_from_list" },
    serverState: visitedRemote });
  assert.equal(result.status, "removed_locally_non_atomic");
  assert.equal(JSON.parse(x.data.taiwan_art_visited).a, undefined);
  assert.ok(JSON.parse(x.data.taiwan_art_favs).a);
});
