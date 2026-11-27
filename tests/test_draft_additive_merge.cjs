const test = require("node:test");
const assert = require("node:assert/strict");
const { plan } = require("../static/js/draft_additive_merge.js");
const fav = { title: "Exhibition", museum: "Museum", dates: "2026", url: "" };
const visited = "2026-11-22T12:34:56.000Z";
const entry = (value, deleted = false) => ({ value, deleted, revision: 1 });
const state = (favs = {}, visits = {}, revision = 1) => ({ revision, favs, visited: visits });
function storage(favs = {}, visits = {}) {
  const data = { taiwan_art_favs: JSON.stringify(favs),
    taiwan_art_visited: JSON.stringify(visits) };
  return { getItem(key) { return data[key] ?? null; },
    setItem() { throw Error("must not write"); },
    removeItem() { throw Error("must not delete"); } };
}
test("different registrations on each device are retained", () => {
  const result = plan(storage({ local: fav }), state({ remote: entry(fav) }));
  assert.equal(result.status, "prepared");
  assert.equal(result.preservedRemote[0].key, "remote");
  assert.deepEqual(JSON.parse(JSON.stringify(result.changes.favs.local)), { set: fav });
  assert.equal(result.review.length, 0);
});
test("same exhibition deduplicates without write", () => {
  const result = plan(storage({ a: fav }), state({ a: entry(fav) }));
  assert.equal(Object.keys(result.changes.favs).length, 0);
  assert.equal(result.same.length, 1);
});
test("local absence never deletes remote registration", () => {
  const result = plan(storage(), state({ a: entry(fav) }));
  assert.equal(result.status, "prepared");
  assert.equal(result.preservedRemote.length, 1);
});
test("explicit deletion conflicts with local registration and requires review", () => {
  const result = plan(storage({ a: fav }), state({ a: entry(null, true) }));
  assert.equal(result.status, "needs_review");
  assert.equal(result.review[0].reason, "explicit_deletion_conflict");
  assert.equal(Object.keys(result.changes.favs).length, 0);
});
test("remote tombstone without local registration stays deleted", () => {
  const result = plan(storage(), state({ a: entry(null, true) }));
  assert.equal(result.status, "prepared");
  assert.equal(result.review.length, 0);
});
test("different metadata never overwrites a saved exhibition", () => {
  const result = plan(storage({ a: fav }), state({ a: entry({ ...fav, museum: "Another" }) }));
  assert.equal(result.status, "prepared");
  assert.equal(result.metadataDifferences.length, 1);
  assert.equal(Object.keys(result.changes.favs).length, 0);
});
test("different visited timestamps preserve both registration intent and server value", () => {
  const result = plan(storage({}, { a: visited }),
    state({}, { a: entry("2026-11-21T12:34:56.000Z") }));
  assert.equal(result.metadataDifferences.length, 1);
  assert.equal(result.review.length, 0);
});
test("local-only visited record is an additive set", () => {
  const result = plan(storage({}, { a: visited }), state());
  assert.deepEqual(result.changes.visited.a, { set: visited });
});
test("invalid local storage cannot be silently treated as empty", () => {
  assert.equal(plan({ getItem() { return "{"; } }, state()).status, "invalid_local");
});
test("invalid server state blocks planning", () => {
  assert.equal(plan(storage(), { revision: "wrong" }).status, "invalid_server");
});
test("conflicts do not discard unrelated additive changes", () => {
  const result = plan(storage({ a: fav, b: fav }), state({ a: entry(null, true) }));
  assert.equal(result.status, "needs_review");
  assert.ok(result.changes.favs.b);
  assert.equal(result.changes.favs.a, undefined);
});

test("same exhibition key in favorites and visited is reconciled independently", () => {
  const result = plan(storage({ a: fav }, { a: visited }),
    state({ a: entry(fav) }, {}, 2));
  assert.equal(result.status, "prepared");
  assert.equal(result.same.length, 1);
  assert.equal(result.same[0].kind, "favs");
  assert.deepEqual(JSON.parse(JSON.stringify(result.changes.visited.a)), { set: visited });
  assert.equal(Object.keys(result.changes.favs).length, 0);
});
test("a deletion conflict in visited never erases an unrelated favorite", () => {
  const result = plan(storage({ keep: fav }, { deleted: visited }),
    state({}, { deleted: entry(null, true) }, 5));
  assert.equal(result.status, "needs_review");
  assert.deepEqual(result.review.map(({kind,key,reason}) => ({kind,key,reason})),
    [{kind:"visited",key:"deleted",reason:"explicit_deletion_conflict"}]);
  assert.deepEqual(JSON.parse(JSON.stringify(result.changes.favs.keep)), {set:fav});
  assert.equal(Object.keys(result.changes.visited).length, 0);
});
test("server registrations remain preserved even if a different local record needs review", () => {
  const result = plan(storage({ conflict: fav }),
    state({ conflict: entry(null,true), remote: entry(fav) }, {}, 9));
  assert.equal(result.status, "needs_review");
  assert.deepEqual(result.preservedRemote.map(x=>x.key), ["remote"]);
  assert.equal(Object.keys(result.changes.favs).length, 0);
});
