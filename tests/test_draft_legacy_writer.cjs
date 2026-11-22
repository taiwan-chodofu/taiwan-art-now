const test = require("node:test");
const assert = require("node:assert/strict");
const { mutate, LOCK_NAME } = require("../static/js/draft_legacy_writer.js");
const fav = { title: "A", museum: "M", region: "Tainan", event: "" };
function fixture() {
  const data = { taiwan_art_favs: JSON.stringify({ a: fav }), taiwan_art_visited: "{}" };
  const storage = { getItem: k => data[k] ?? null, setItem: (k,v) => { data[k] = v; } };
  let tail = Promise.resolve();
  const locks = { request(name, opts, fn) {
    assert.equal(name, LOCK_NAME); assert.equal(opts.mode, "exclusive");
    const p = tail.then(fn); tail = p.catch(() => {}); return p;
  }};
  return { data, storage, locks };
}
test("two concurrent tab additions preserve both items", async () => {
  const x = fixture();
  const results = await Promise.all([
    mutate({ ...x, kind: "favs", key: "b", action: "set", value: { ...fav, title: "B" } }),
    mutate({ ...x, kind: "favs", key: "c", action: "set", value: { ...fav, title: "C" } })
  ]);
  assert.ok(results.every(r => r.status === "written_under_cooperative_lock"));
  assert.deepEqual(Object.keys(JSON.parse(x.data.taiwan_art_favs)), ["a","b","c"]);
});
test("remove one item while adding another preserves new addition", async () => {
  const x = fixture();
  await Promise.all([
    mutate({ ...x, kind: "favs", key: "a", action: "remove" }),
    mutate({ ...x, kind: "favs", key: "b", action: "set", value: fav })
  ]);
  assert.deepEqual(Object.keys(JSON.parse(x.data.taiwan_art_favs)), ["b"]);
});
test("mixed visited shapes can be written without changing existing record", async () => {
  const x = fixture();
  const object = { date: "2026-11-22T00:00:00Z", title: "A", museum: "M" };
  await mutate({ ...x, kind: "visited", key: "a", action: "set", value: object });
  await mutate({ ...x, kind: "visited", key: "b", action: "set",
    value: "2026-11-22T00:00:00Z" });
  const visited = JSON.parse(x.data.taiwan_art_visited);
  assert.deepEqual(visited.a, object);
  assert.equal(typeof visited.b, "string");
});
test("missing lock fails closed", async () => {
  const x = fixture();
  assert.equal((await mutate({ ...x, locks: null, kind: "favs", key: "b",
    action: "set", value: fav })).status, "not_authorized");
  assert.deepEqual(Object.keys(JSON.parse(x.data.taiwan_art_favs)), ["a"]);
});
test("invalid visited value does not write", async () => {
  const x = fixture();
  assert.equal((await mutate({ ...x, kind: "visited", key: "a",
    action: "set", value: { title: "No date" } })).status, "unavailable");
  assert.equal(x.data.taiwan_art_visited, "{}");
});
test("absent removal is no-op, not a tombstone", async () => {
  const x = fixture();
  assert.equal((await mutate({ ...x, kind: "favs", key: "absent",
    action: "remove" })).status, "unchanged");
});

test("legacy-tab write detected before setItem aborts without clobbering", async () => {
  const x = fixture();
  let reads = 0;
  const original = x.storage.getItem;
  x.storage.getItem = key => {
    reads++;
    if (reads === 4) x.data.taiwan_art_favs = JSON.stringify({ a: fav, legacy: fav });
    return original(key);
  };
  const result = await mutate({ ...x, kind: "favs", key: "new", action: "set", value: fav });
  assert.equal(result.status, "stale_local");
  assert.deepEqual(Object.keys(JSON.parse(x.data.taiwan_art_favs)), ["a", "legacy"]);
});
