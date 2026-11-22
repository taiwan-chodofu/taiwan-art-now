/* Node built-in test runner, synthetic data only. */
const test = require("node:test");
const assert = require("node:assert/strict");
const { plan, synchronize } = require("../static/js/draft_versioned_sync.js");
const local = (favs = {}, visited = {}) => ({ favs, visited });
const server = (favs = {}, visited = {}, revision = 1) => ({ revision, favs, visited });
const entry = (value, deleted = false, revision = 1) => ({ value, deleted, revision });
const reply = (body, status = 200) => ({
  status, ok: status >= 200 && status < 300, json: async () => body
});

test("new local item produces set only", () => {
  const p = plan(local({ a: true }), server());
  assert.equal(p.safeToWrite, true);
  assert.deepEqual(p.changes.favs.a, { set: true });
});
test("equal remote item requires no write", () => {
  const p = plan(local({ a: true }), server({ a: entry(true) }));
  assert.equal(p.safeToWrite, true);
  assert.equal(Object.keys(p.changes.favs).length, 0);
});
test("remote-only item blocks write rather than deleting it", () => {
  const p = plan(local(), server({ a: entry(true) }));
  assert.equal(p.safeToWrite, false);
  assert.deepEqual(p.remoteOnly.favs, ["a"]);
});
test("remote tombstone blocks stale local resurrection", () => {
  const p = plan(local({ a: true }), server({ a: entry(null, true) }));
  assert.equal(p.safeToWrite, false);
  assert.deepEqual(p.conflicts.favs, ["a"]);
});
test("different values block automatic write", () => {
  assert.equal(plan(local({ a: false }), server({ a: entry(true) })).safeToWrite, false);
});
test("different visited state also blocks", () => {
  assert.equal(plan(local({}, { a: false }),
    server({}, { a: entry(true) })).safeToWrite, false);
});
test("offline leaves local data untouched", async () => {
  const data = local({ a: true });
  const before = JSON.stringify(data);
  const result = await synchronize({ localSnapshot: data, fetchImpl: async () => {
    throw new Error("offline");
  } });
  assert.equal(result.status, "offline");
  assert.equal(JSON.stringify(data), before);
});
test("GET forbidden never sends POST", async () => {
  let count = 0;
  const result = await synchronize({ localSnapshot: local({ a: true }),
    fetchImpl: async () => { count++; return reply({}, 403); } });
  assert.equal(result.status, "unauthorized");
  assert.equal(count, 1);
});
test("409 never retries stale changes", async () => {
  const methods = [];
  const result = await synchronize({ localSnapshot: local({ a: true }),
    fetchImpl: async (_, options) => {
      methods.push(options.method);
      return methods.length === 1 ? reply(server()) : reply({}, 409);
    } });
  assert.equal(result.status, "stale_revision");
  assert.deepEqual(methods, ["GET", "POST"]);
});
test("unknown commit after POST timeout never retries", async () => {
  let calls = 0;
  const result = await synchronize({ localSnapshot: local({ a: true }),
    fetchImpl: async () => {
      calls++;
      if (calls === 1) return reply(server());
      throw new Error("network dropped after write");
    } });
  assert.equal(result.status, "unknown_commit");
  assert.equal(calls, 2);
});
test("no POST when remote-only exists", async () => {
  let calls = 0;
  const result = await synchronize({ localSnapshot: local(),
    fetchImpl: async () => { calls++; return reply(server({ a: entry(true) })); } });
  assert.equal(result.status, "needs_review");
  assert.equal(calls, 1);
});
test("rejects identity fields in local snapshot", () => {
  assert.throws(() => plan({ ...local(), sender_id: "victim" }, server()));
});
test("rejects prototype-polluting item key", () => {
  const favs = Object.create(null);
  favs.__proto__ = true;
  assert.throws(() => plan(local(favs), server()));
});
test("successful write sends no identity and uses credentials", async () => {
  let sent;
  const result = await synchronize({ localSnapshot: local({ a: true }),
    fetchImpl: async (_, options) => {
      if (options.method === "GET") return reply(server());
      sent = options;
      return reply(server({ a: entry(true) }, {}, 2));
    } });
  assert.equal(result.status, "saved");
  assert.equal(sent.credentials, "same-origin");
  assert.deepEqual(JSON.parse(sent.body), {
    base_revision: 1, changes: { favs: { a: { set: true } }, visited: {} }
  });
});
test("invalid server state does not POST", async () => {
  let calls = 0;
  const result = await synchronize({ localSnapshot: local(),
    fetchImpl: async () => { calls++; return reply({ revision: "bad" }); } });
  assert.equal(result.status, "invalid_server");
  assert.equal(calls, 1);
});
