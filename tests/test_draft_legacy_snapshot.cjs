const test = require("node:test");
const assert = require("node:assert/strict");
const { read, validateMap } = require("../static/js/draft_legacy_snapshot.js");
const favorite = { title: "Exhibition", museum: "Museum", dates: "2026", url: "/exhibition/a" };
const iso = "2026-11-22T12:34:56.000Z";
function storage(data) {
  return { getItem(key) { return Object.prototype.hasOwnProperty.call(data, key) ? data[key] : null; } };
}
test("reads actual legacy object maps without writing", () => {
  const data = { taiwan_art_favs: JSON.stringify({ a: favorite }),
    taiwan_art_visited: JSON.stringify({ b: iso }) };
  const result = read(storage(data));
  assert.equal(result.status, "ready");
  assert.equal(result.snapshot.favs.a.title, "Exhibition");
  assert.equal(result.snapshot.visited.b, iso);
});
test("missing keys yield empty maps without deletions", () => {
  const result = read(storage({}));
  assert.equal(result.status, "ready");
  assert.equal(Object.keys(result.snapshot.favs).length, 0);
});
test("malformed JSON is reported not replaced", () => {
  assert.deepEqual(read(storage({ taiwan_art_favs: "{" })),
    { status: "invalid_local", kind: "favs" });
});
test("rejects array instead of map", () => {
  assert.throws(() => validateMap([], "favs"));
});
test("rejects bad favorite fields", () => {
  assert.throws(() => validateMap({ a: { ...favorite, sender_id: "victim" } }, "favs"));
});
test("rejects invalid visited timestamp", () => {
  assert.throws(() => validateMap({ a: true }, "visited"));
});
test("rejects missing favorite title", () => {
  assert.throws(() => validateMap({ a: { museum: "M" } }, "favs"));
});
test("rejects prototype pollution keys", () => {
  const data = JSON.parse('{"__proto__":{"title":"x","museum":"m"}}');
  assert.throws(() => validateMap(data, "favs"));
});
test("rejects overly long item keys", () => {
  assert.throws(() => validateMap({ ["x".repeat(513)]: favorite }, "favs"));
});
test("storage exception does not erase data", () => {
  assert.deepEqual(read({ getItem() { throw Error("blocked"); } }),
    { status: "unavailable" });
});
test("preserves existing timestamps exactly", () => {
  const result = read(storage({ taiwan_art_visited: JSON.stringify({ a: iso }) }));
  assert.equal(result.snapshot.visited.a, iso);
});
test("preserves optional favorite metadata", () => {
  const result = read(storage({ taiwan_art_favs: JSON.stringify({ a: favorite }) }));
  assert.equal(result.snapshot.favs.a.url, favorite.url);
  assert.equal(result.snapshot.favs.a.dates, favorite.dates);
});
