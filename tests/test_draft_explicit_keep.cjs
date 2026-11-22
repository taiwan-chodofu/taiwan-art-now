const test = require("node:test");
const assert = require("node:assert/strict");
const { execute } = require("../static/js/draft_explicit_keep.js");
const decision = { kind: "favs", key: "a", choice: "keep_saved" };
const conflict = { kind: "favs", key: "a",
  reason: "explicit_deletion_conflict", itemRevision: 3 };
function args(overrides = {}) {
  return { decision, conflict, localValue: { title: "A" }, baseRevision: 4,
    request: async () => { throw Error("request not stubbed"); }, ...overrides };
}
test("explicit keep sends only issue then consume", async () => {
  const calls = [];
  const result = await execute(args({ request: async (url, payload) => {
    calls.push([url, payload]);
    return calls.length === 1 ? { token: "synthetic" } : { revision: 5 };
  }}));
  assert.equal(result.status, "submitted");
  assert.equal(calls.length, 2);
  assert.match(calls[0][0], /review\/keep\/issue$/);
  assert.match(calls[1][0], /review\/keep\/consume$/);
  assert.equal(calls[0][1].reviewed_item_revision, 3);
  assert.equal(calls[1][1].token, "synthetic");
});
for (const choice of ["decide_later", "remove_from_list"]) {
  test(choice + " never sends requests", async () => {
    let count = 0;
    const result = await execute(args({ decision: { ...decision, choice },
      request: async () => { count++; } }));
    assert.equal(result.status, "not_authorized");
    assert.equal(count, 0);
  });
}
test("unrelated exhibition cannot use decision", async () => {
  assert.equal((await execute(args({ conflict: { ...conflict, key: "b" } })).status),
    "not_authorized");
});
test("non-tombstone conflict cannot issue token", async () => {
  assert.equal((await execute(args({ conflict: { ...conflict,
    reason: "metadata_diff_preserved" } })).status), "not_authorized");
});
test("invalid item revision cannot issue token", async () => {
  assert.equal((await execute(args({ conflict: { ...conflict,
    itemRevision: 7 } })).status), "not_authorized");
});
test("missing saved value cannot issue token", async () => {
  assert.equal((await execute(args({ localValue: null })).status), "not_authorized");
});
test("failed issue never attempts consume", async () => {
  let count = 0;
  const result = await execute(args({ request: async () => { count++; return {}; } }));
  assert.equal(result.status, "issue_failed");
  assert.equal(count, 1);
});
