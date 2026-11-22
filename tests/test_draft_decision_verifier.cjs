const test = require("node:test");
const assert = require("node:assert/strict");
const { verify } = require("../static/js/draft_decision_verifier.js");
const fav = { title: "A", museum: "M", dates: "", url: "" };
const other = { ...fav, museum: "N" };
const record = (value, deleted = false) => ({ value, deleted, revision: 1 });
function storage(favs = {}, visited = {}) {
  const data = { taiwan_art_favs: JSON.stringify(favs),
    taiwan_art_visited: JSON.stringify(visited) };
  return { getItem(key) { return data[key]; },
    setItem() { throw Error("unexpected storage write"); } };
}
const state = (favs = {}, visited = {}, revision = 1) =>
  ({ revision, favs, visited });
const decision = (choice, key = "a", kind = "favs") => ({ choice, key, kind });
function run(local, remote, decisions = [], expectedRevision = 1) {
  return verify({ storage: local, serverState: remote, decisions, expectedRevision });
}
test("stale revision blocks proposals", () => {
  assert.equal(run(storage({ a: fav }), state({ a: record(other) }),
    [decision("keep_local")], 0).status, "stale_revision");
});
test("conflicting value needs explicit choice", () => {
  const result = run(storage({ a: fav }), state({ a: record(other) }));
  assert.equal(result.status, "requires_review");
  assert.equal(result.proposals.length, 0);
});
test("explicit local choice creates preview only", () => {
  const result = run(storage({ a: fav }), state({ a: record(other) }),
    [decision("keep_local")]);
  assert.equal(result.status, "prepared");
  assert.deepEqual(result.proposals, [{ kind: "favs", key: "a",
    action: "set", expectedItemRevision: 1 }]);
});
test("remote choice remains pending until safe local apply exists", () => {
  const result = run(storage({ a: fav }), state({ a: record(other) }),
    [decision("keep_remote")]);
  assert.equal(result.status, "requires_review");
  assert.equal(result.unresolved[0].reason, "local_apply_not_implemented");
});
test("remote tombstone cannot be resurrected", () => {
  const result = run(storage({ a: fav }), state({ a: record(null, true) }),
    [decision("keep_local")]);
  assert.equal(result.status, "requires_review");
  assert.equal(result.unresolved[0].reason, "tombstone_requires_separate_confirmation");
});
test("remote-only record cannot be deleted by local absence", () => {
  const result = run(storage(), state({ a: record(fav) }),
    [decision("keep_local")]);
  assert.equal(result.unresolved[0].reason, "local_absence_not_deletion");
});
test("duplicate decisions rejected", () => {
  assert.equal(run(storage({ a: fav }), state({ a: record(other) }),
    [decision("keep_local"), decision("keep_remote")]).status, "invalid_decisions");
});
test("unknown decision rejected", () => {
  assert.equal(run(storage(), state(), [decision("keep_local")]).status, "invalid_decisions");
});
test("extra identity property rejected", () => {
  assert.equal(run(storage({ a: fav }), state({ a: record(other) }),
    [{ ...decision("keep_local"), sender_id: "victim" }]).status, "invalid_decisions");
});
test("local-only addition is previewed", () => {
  const result = run(storage({ a: fav }), state());
  assert.equal(result.status, "prepared");
  assert.equal(result.proposals[0].expectedItemRevision, null);
});
test("invalid local data is never overwritten", () => {
  const broken = { getItem() { return "{"; } };
  assert.equal(run(broken, state()).status, "invalid_local");
});
test("no changes yields empty prepared proposal", () => {
  const result = run(storage(), state());
  assert.equal(result.status, "prepared");
  assert.deepEqual(result.proposals, []);
});
