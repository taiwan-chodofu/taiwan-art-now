const test = require("node:test");
const assert = require("node:assert/strict");
const { read } = require("../static/js/draft_legacy_snapshot.js");
function storage(favs, visited) {
  return { getItem: key => key === "taiwan_art_favs" ?
    JSON.stringify(favs) : JSON.stringify(visited) };
}
const fav = { title: "A", museum: "M", dates: "2026", url: "/a",
  region: "Tainan", event: "Opening" };
const visitedObject = { date: "2026-11-22T00:00:00.000Z", title: "A",
  museum: "M", dates: "2026", url: "/a", region: "Tainan" };
test("main/discover object visited record is preserved intact", () => {
  const result = read(storage({ a: fav }, { a: visitedObject }));
  assert.equal(result.status, "ready");
  assert.deepEqual({ ...result.snapshot.visited.a }, visitedObject);
  assert.deepEqual({ ...result.snapshot.favs.a }, fav);
});
test("nearby/detail ISO string visited record remains supported", () => {
  const result = read(storage({}, { a: "2026-11-22T00:00:00.000Z" }));
  assert.equal(result.status, "ready");
  assert.equal(result.snapshot.visited.a, "2026-11-22T00:00:00.000Z");
});
test("mixed visited shapes are preserved without coercion", () => {
  const result = read(storage({}, { a: visitedObject,
    b: "2026-11-22T00:00:00.000Z" }));
  assert.equal(result.status, "ready");
  assert.equal(typeof result.snapshot.visited.a, "object");
  assert.equal(typeof result.snapshot.visited.b, "string");
});
test("visited object with missing date is rejected", () => {
  assert.equal(read(storage({}, { a: { title: "A" } })).status, "invalid_local");
});
test("visited object with unexpected field is rejected", () => {
  assert.equal(read(storage({}, { a: { ...visitedObject, injected: "x" } })).status, "invalid_local");
});
test("favorite unknown metadata is still rejected", () => {
  assert.equal(read(storage({ a: { ...fav, injected: "x" } }, {})).status, "invalid_local");
});
