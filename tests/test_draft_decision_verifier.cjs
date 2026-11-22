const test = require("node:test");
const assert = require("node:assert/strict");
const { verify } = require("../static/js/draft_decision_verifier.js");
const { read } = require("../static/js/draft_legacy_snapshot.js");
const fav = { title: "A", museum: "M", dates: "", url: "" };
const record = (value, deleted = false) => ({ value, deleted, revision: 1 });
function storage(favs = {}, visited = {}) {
  const data = { taiwan_art_favs: JSON.stringify(favs), taiwan_art_visited: JSON.stringify(visited) };
  return { getItem(key) { return data[key]; },
    setItem() { throw Error("unexpected storage write"); } };
}
const state = (favs = {}, visited = {}, revision = 1) => ({ revision, favs, visited });
const decision = (choice, key = "a", kind = "favs") => ({ choice, key, kind });
function run(local, remote, decisions = [], expectedRevision = 1, overrides = {}) {
  return verify({ storage: local, serverState: remote, decisions, expectedRevision,
    expectedLocalSnapshot: read(local).snapshot, ...overrides });
}
test("stale server revision blocks proposals", () => {
  assert.equal(run(storage({ a: fav }), state({ a: record(null, true) }),
    [decision("keep_saved")], 0).status, "stale_revision");
});
test("stale local snapshot blocks decisions", () => {
  const original = read(storage()).snapshot;
  assert.equal(run(storage({ a: fav }), state({ a: record(null, true) }),
    [decision("keep_saved")], 1, { expectedLocalSnapshot: original }).status, "stale_local_snapshot");
});
test("missing reviewed local snapshot fails closed", () => {
  assert.equal(run(storage(), state(), [], 1, { expectedLocalSnapshot: undefined }).status,
    "stale_local_snapshot");
});
test("tombstone requires explicit choice", () => {
  const result = run(storage({ a: fav }), state({ a: record(null, true) }));
  assert.equal(result.status, "requires_review");
  assert.equal(result.proposals.length, 0);
});
test("explicit keep_saved proposes authenticated CAS only", () => {
  const result = run(storage({ a: fav }), state({ a: record(null, true) }),
    [decision("keep_saved")]);
  assert.equal(result.status, "prepared");
  assert.deepEqual(result.proposals, [{ kind: "favs", key: "a", action: "set",
    expectedItemRevision: 1, requiresAuthenticatedCAS: true }]);
});
test("remove_from_list cannot silently mutate local storage", () => {
  const result = run(storage({ a: fav }), state({ a: record(null, true) }),
    [decision("remove_from_list")]);
  assert.equal(result.status, "requires_review");
  assert.equal(result.unresolved[0].reason, "local_removal_not_implemented");
});
test("legacy missing entry does not imply deletion", () => {
  const result = run(storage(), state({ a: record(fav) }));
  assert.equal(result.status, "prepared");
  assert.deepEqual(result.proposals, []);
});
test("metadata difference does not require review", () => {
  const result = run(storage({ a: fav }),
    state({ a: record({ ...fav, museum: "N" }) }));
  assert.equal(result.status, "prepared");
  assert.deepEqual(result.proposals, []);
});
test("duplicate decisions are rejected", () => {
  assert.equal(run(storage({ a: fav }), state({ a: record(null, true) }),
    [decision("keep_saved"), decision("keep_saved")]).status, "invalid_decisions");
});
test("old device/server choices are rejected", () => {
  assert.equal(run(storage({ a: fav }), state({ a: record(null, true) }),
    [decision("keep_local")]).status, "invalid_decisions");
});
test("identity-bearing choices are rejected", () => {
  assert.equal(run(storage({ a: fav }), state({ a: record(null, true) }),
    [{ ...decision("keep_saved"), sender_id: "victim" }]).status, "invalid_decisions");
});
test("unknown records are rejected", () => {
  assert.equal(run(storage(), state(), [decision("keep_saved")]).status, "invalid_decisions");
});
test("local-only addition is an authenticated CAS proposal", () => {
  const result = run(storage({ a: fav }), state());
  assert.equal(result.status, "prepared");
  assert.deepEqual(result.proposals, [{ kind: "favs", key: "a", action: "set",
    expectedItemRevision: null, requiresAuthenticatedCAS: true }]);
});
test("invalid local data is not treated as empty", () => {
  const broken = { getItem() { return "{"; } };
  assert.equal(verify({ storage: broken, serverState: state(),
    expectedRevision: 1, expectedLocalSnapshot: {}, decisions: [] }).status, "invalid_local");
});
test("decide_later leaves tombstone intact", () => {
  const result = run(storage({ a: fav }), state({ a: record(null, true) }),
    [decision("decide_later")]);
  assert.equal(result.status, "requires_review");
  assert.equal(result.proposals.length, 0);
});
test("visited tombstone has independent decision", () => {
  const result = run(storage({}, { a: "2026-11-22T12:00:00.000Z" }),
    state({}, { a: record(null, true) }), [decision("keep_saved", "a", "visited")]);
  assert.equal(result.proposals[0].kind, "visited");
});
