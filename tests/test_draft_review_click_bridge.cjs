const test = require("node:test");
const assert = require("node:assert/strict");
const { mount } = require("../static/js/draft_review_click_bridge.js");
const { read } = require("../static/js/draft_legacy_snapshot.js");
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.value = ""; this.events = {}; this.textContent = ""; }
  setAttribute() {}
  appendChild(child) { this.children.push(child); return child; }
  addEventListener(name, fn) { this.events[name] = fn; }
  remove() { this.removed = true; }
}
const doc = { createElement: tag => new Element(tag) };
const fav = { title: "A", museum: "M", dates: "", url: "" };
const serverState = { revision: 3, favs: { a: { value: null, deleted: true, revision: 2 } }, visited: {} };
const report = { status: "needs_review", review: [{ kind: "favs", key: "a", reason: "explicit_deletion_conflict" }] };
const elements = (root, tag) => [root, ...root.children.flatMap(x => elements(x, tag))].filter(x => x.tag === tag);
function setup() {
  const data = { taiwan_art_favs: JSON.stringify({ a: fav }), taiwan_art_visited: "{}" };
  const storage = { getItem: key => data[key] };
  const calls = [];
  const request = async (url, payload) => {
    calls.push([url, payload]);
    return calls.length % 2 ? { token: "synthetic" } : { revision: 4 };
  };
  const container = new Element("main");
  const instance = mount({ container, report, doc, serverState, storage,
    localSnapshot: read(storage).snapshot, request });
  return { container, instance, calls, data };
}
test("rendering and default defer never sends a request", async () => {
  const x = setup();
  assert.equal(x.calls.length, 0);
  await x.instance.submit();
  assert.equal(x.calls.length, 0);
});
test("selection change alone never sends a request", () => {
  const x = setup();
  const select = elements(x.container, "select")[0];
  select.value = "keep_saved"; select.events.change();
  assert.equal(x.calls.length, 0);
});
test("explicit click triggers issue then consume", async () => {
  const x = setup();
  const select = elements(x.container, "select")[0];
  select.value = "keep_saved"; select.events.change();
  await elements(x.container, "button")[0].events.click();
  assert.equal(x.calls.length, 2);
  assert.match(x.calls[0][0], /issue$/);
  assert.match(x.calls[1][0], /consume$/);
});
test("remove never sends requests", async () => {
  const x = setup();
  const select = elements(x.container, "select")[0];
  select.value = "remove_from_list"; select.events.change();
  await x.instance.submit();
  assert.equal(x.calls.length, 0);
});
test("changed local snapshot blocks confirmation", async () => {
  const x = setup();
  const select = elements(x.container, "select")[0];
  select.value = "keep_saved"; select.events.change();
  x.data.taiwan_art_favs = "{}";
  await x.instance.submit();
  assert.equal(x.calls.length, 0);
});
test("disposed review blocks click submission", async () => {
  const x = setup();
  x.instance.dispose();
  await x.instance.submit();
  assert.equal(x.calls.length, 0);
});
test("ordinary merge creates no button", () => {
  const data = { taiwan_art_favs: "{}", taiwan_art_visited: "{}" };
  const storage = { getItem: key => data[key] };
  const container = new Element("main");
  const instance = mount({ container, doc, storage, serverState,
    localSnapshot: read(storage).snapshot,
    report: { status: "prepared", review: [] },
    request: async () => { throw Error("unexpected"); } });
  assert.equal(instance.rendered, false);
  assert.equal(container.children.length, 0);
});
