const test = require("node:test");
const assert = require("node:assert/strict");
const { createReview } = require("../static/js/draft_conflict_review_ui.js");
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.attributes = {}; this.value = ""; this.textContent = ""; this.events = {}; }
  setAttribute(k, v) { this.attributes[k] = v; }
  appendChild(child) { this.children.push(child); return child; }
  addEventListener(event, callback) { this.events[event] = callback; }
  remove() { this.removed = true; }
}
const doc = { createElement(tag) { return new Element(tag); } };
const row = (status, key = "sample") => ({ kind: "favs", key, status });
const report = rows => ({ status: "ready", rows });
function elements(root, tag) {
  return [root, ...root.children.flatMap(child => elements(child, tag))]
    .filter(element => element.tag === tag);
}
test("renders conflict using textContent, not HTML injection", () => {
  const container = new Element("main");
  createReview(container, report([row("different", "<img src=x onerror=alert(1)>")]), doc);
  assert.equal(elements(container, "img").length, 0);
  assert.ok(elements(container, "p").some(el => el.textContent.includes("<img")));
});
test("defaults to decide later and never persists", () => {
  const container = new Element("main");
  const ui = createReview(container, report([row("remote_only")]), doc);
  assert.deepEqual(ui.getDecisions(), [{ kind: "favs", key: "sample", choice: "decide_later" }]);
});
test("user selection changes only in-memory draft", () => {
  const container = new Element("main");
  const ui = createReview(container, report([row("different")]), doc);
  const select = elements(container, "select")[0];
  select.value = "keep_remote";
  select.events.change();
  assert.equal(ui.getDecisions()[0].choice, "keep_remote");
});
test("rejects unknown choice values", () => {
  const container = new Element("main");
  const ui = createReview(container, report([row("different")]), doc);
  const select = elements(container, "select")[0];
  select.value = "delete_all";
  select.events.change();
  assert.equal(ui.getDecisions()[0].choice, "decide_later");
});
test("renders only actionable conflicts", () => {
  const container = new Element("main");
  const ui = createReview(container, report([
    row("same"), row("local_only", "a"), row("remote_tombstone", "b"),
    row("deleted_remotely", "c")
  ]), doc);
  assert.equal(elements(container, "select").length, 1);
  assert.equal(ui.getDecisions()[0].key, "c");
});
test("visited conflicts are distinct from favorites", () => {
  const container = new Element("main");
  const ui = createReview(container, report([
    row("different", "same"), { ...row("different", "same"), kind: "visited" }
  ]), doc);
  assert.equal(ui.getDecisions().length, 2);
});
test("rejects invalid report", () => {
  assert.throws(() => createReview(new Element("main"), { status: "invalid_local" }, doc));
});
test("dispose removes only the generated review section", () => {
  const container = new Element("main");
  const ui = createReview(container, report([]), doc);
  ui.dispose();
  assert.equal(container.children[0].removed, true);
});
