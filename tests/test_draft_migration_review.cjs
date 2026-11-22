const test = require("node:test");
const assert = require("node:assert/strict");
const { preview, prepareBootstrap } = require("../static/js/draft_migration_review.js");
const fav = { title: "Show", museum: "Museum", dates: "2026", url: "" };
const iso = "2026-11-22T12:34:56.000Z";
const entry = (value, deleted = false, revision = 1) => ({ value, deleted, revision });
const state = (favs = {}, visited = {}, revision = 1) => ({ revision, favs, visited });
function storage(favs, visited) {
  const values = { taiwan_art_favs: JSON.stringify(favs),
    taiwan_art_visited: JSON.stringify(visited) };
  return { getItem(key) { return values[key] ?? null; },
    setItem() { throw Error("unexpected write"); },
    removeItem() { throw Error("unexpected delete"); } };
}
test("existing metadata and timestamp are recognized as same", () => {
  const result = preview(storage({ a: fav }, { b: iso }),
    state({ a: entry(fav) }, { b: entry(iso) }));
  assert.equal(result.status, "ready");
  assert.equal(result.counts.same, 2);
  assert.equal(result.safeToWrite, true);
});
test("local-only item is reported without changing local storage", () => {
  const result = preview(storage({ a: fav }, {}), state());
  assert.equal(result.counts.local_only, 1);
  assert.equal(result.rows[0].localPresent, true);
});
test("remote-only item blocks silent overwrite", () => {
  const result = preview(storage({}, {}), state({ a: entry(fav) }));
  assert.equal(result.counts.remote_only, 1);
  assert.equal(result.safeToWrite, false);
});
test("remote deletion cannot resurrect a stale local item", () => {
  const result = preview(storage({ a: fav }, {}),
    state({ a: entry(null, true) }));
  assert.equal(result.counts.deleted_remotely, 1);
  assert.equal(result.safeToWrite, false);
});
test("remote tombstone without local item is retained", () => {
  const result = preview(storage({}, {}), state({ a: entry(null, true) }));
  assert.equal(result.counts.remote_tombstone, 1);
});
test("different metadata requires review", () => {
  const result = preview(storage({ a: fav }, {}),
    state({ a: entry({ ...fav, museum: "Other" }) }));
  assert.equal(result.counts.different, 1);
  assert.equal(result.safeToWrite, false);
});
test("different visited timestamp requires review", () => {
  const result = preview(storage({}, { a: iso }),
    state({}, { a: entry("2026-11-23T12:34:56.000Z") }));
  assert.equal(result.counts.different, 1);
});
test("invalid local data is not silently reset", () => {
  const result = preview({ getItem() { return "{"; } }, state());
  assert.equal(result.status, "invalid_local");
});
test("invalid server state is rejected", () => {
  assert.equal(preview(storage({}, {}), { revision: "bad" }).status, "invalid_server");
});
test("does not expose item values in summary rows", () => {
  const result = preview(storage({ a: fav }, {}), state());
  assert.equal(JSON.stringify(result.rows).includes("Museum"), false);
});
test("does not infer local deletion from absence", () => {
  const result = preview(storage({}, {}), state({ a: entry(fav) }));
  assert.equal(result.rows[0].status, "remote_only");
});
test("two collections remain independent", () => {
  const result = preview(storage({ a: fav }, { a: iso }), state());
  assert.equal(result.rows.length, 2);
  assert.equal(result.counts.local_only, 2);
});

test("bootstrap preserves exact legacy favorite metadata and visited timestamp", () => {
  const result = prepareBootstrap(storage({ a: fav }, { b: iso }),
    state({}, {}, 0));
  assert.equal(result.status, "prepared");
  assert.deepEqual(JSON.parse(JSON.stringify(result.changes.favs.a)), { set: fav });
  assert.deepEqual(result.changes.visited.b, { set: iso });
  assert.equal(result.base_revision, 0);
});
test("bootstrap refuses populated server even if local matches", () => {
  const result = prepareBootstrap(storage({ a: fav }, {}),
    state({ a: entry(fav) }));
  assert.equal(result.status, "requires_review");
});
test("bootstrap refuses nonzero revision even if server has no items", () => {
  const result = prepareBootstrap(storage({}, {}), state({}, {}, 1));
  assert.equal(result.status, "requires_review");
});
test("bootstrap refuses tombstoned server records", () => {
  const result = prepareBootstrap(storage({ a: fav }, {}),
    state({ a: entry(null, true) }));
  assert.equal(result.status, "requires_review");
});
