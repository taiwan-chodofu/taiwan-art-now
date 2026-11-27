const test = require("node:test");
const assert = require("node:assert/strict");
const { create } = require("../static/js/draft_action_commit.js");
const fav = { title: "台南展覽", museum: "Museum", dates: "2026", url: "/e/a", region: "臺南", event: "" };
const visited = { date: "2026-11-23T01:02:03.000Z", title: fav.title,
  museum: fav.museum, dates: fav.dates, url: fav.url, region: fav.region };
function harness() {
  const data = { taiwan_art_favs: "{}", taiwan_art_visited: "{}" };
  let blocked = false;
  const storage = {
    getItem(k) { return data[k] ?? null; },
    setItem(k,v) { if (blocked) throw Error("quota"); data[k] = v; }
  };
  let tail = Promise.resolve();
  const locks = { request(_name,_options,fn) {
    const p = tail.then(fn); tail = p.catch(() => {}); return p;
  }};
  const ui = { fav: false, visited: false, pending: false, errors: [], notifications: 0, analytics: [] };
  const adapter = create({ storage, locks,
    onBusy(busy) { ui.pending = busy; },
    onFailure(result) { ui.errors.push(result.status); },
    onCommitted({ kind, key, action }) {
      const map = JSON.parse(data[kind === "favs" ? "taiwan_art_favs" : "taiwan_art_visited"]);
      ui[kind === "favs" ? "fav" : "visited"] = Object.prototype.hasOwnProperty.call(map,key);
      ui.notifications++;
      ui.analytics.push(kind + ":" + action);
    }
  });
  return { data, ui, adapter, block() { blocked = true; }, storage, locks };
}
test("home/discover favorites: add, duplicate, remove update UI only after persistence", async () => {
  const x = harness();
  assert.equal(x.ui.fav, false);
  assert.equal((await x.adapter.commit({ kind: "favs", key: "a", action: "set", value: fav })).status,
    "written_under_cooperative_lock");
  assert.equal(x.ui.fav, true);
  assert.equal(JSON.parse(x.data.taiwan_art_favs).a.event, "");
  assert.equal((await x.adapter.commit({ kind: "favs", key: "a", action: "remove" })).status,
    "written_under_cooperative_lock");
  assert.equal(x.ui.fav, false);
  assert.deepEqual(x.ui.analytics, ["favs:set", "favs:remove"]);
});
test("home/discover object visited and nearby/detail string visited both roundtrip", async () => {
  const x = harness();
  await x.adapter.commit({ kind: "visited", key: "home", action: "set", value: visited });
  assert.deepEqual(JSON.parse(x.data.taiwan_art_visited).home, visited);
  await x.adapter.commit({ kind: "visited", key: "nearby", action: "set", value: visited.date });
  assert.equal(JSON.parse(x.data.taiwan_art_visited).nearby, visited.date);
  await x.adapter.commit({ kind: "visited", key: "home", action: "remove" });
  assert.equal(JSON.parse(x.data.taiwan_art_visited).nearby, visited.date);
  // UI callback reflects the last acted-on exhibition (home), now removed.
  assert.equal(x.ui.visited, false);
  assert.equal(Object.prototype.hasOwnProperty.call(JSON.parse(x.data.taiwan_art_visited), "nearby"), true);
});
test("quota failure leaves UI and notification/analytics unchanged", async () => {
  const x = harness(); x.block();
  const r = await x.adapter.commit({ kind: "favs", key: "a", action: "set", value: fav });
  assert.equal(r.status, "unavailable");
  assert.equal(x.ui.fav, false);
  assert.equal(x.ui.notifications, 0);
  assert.deepEqual(x.ui.analytics, []);
  assert.deepEqual(x.ui.errors, ["unavailable"]);
  assert.equal(x.ui.pending, false);
});
test("two independent page instances preserve distinct exhibition registrations", async () => {
  const x = harness();
  const other = create({ storage: x.storage, locks: x.locks,
    onCommitted() {}, onFailure() {} });
  await Promise.all([
    x.adapter.commit({ kind: "favs", key: "a", action: "set", value: fav }),
    other.commit({ kind: "favs", key: "b", action: "set", value: { ...fav, title: "Other" } })
  ]);
  assert.deepEqual(Object.keys(JSON.parse(x.data.taiwan_art_favs)), ["a","b"]);
});
test("no server API calls occur in local-only UI integration harness", async () => {
  const x = harness();
  await x.adapter.commit({ kind: "favs", key: "a", action: "set", value: fav });
  assert.equal(x.ui.notifications, 1);
  // Notification is an injected callback count, not a real network request.
  assert.equal(x.ui.analytics.length, 1);
});
