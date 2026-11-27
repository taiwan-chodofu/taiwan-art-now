const test = require("node:test");
const assert = require("node:assert/strict");
const { createReview } = require("../static/js/draft_conflict_review_ui.js");
const { plan } = require("../static/js/draft_additive_merge.js");
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.attributes = {}; this.value = ""; this.textContent = ""; this.events = {}; }
  setAttribute(k, v) { this.attributes[k] = v; }
  appendChild(child) { this.children.push(child); return child; }
  addEventListener(event, callback) { this.events[event] = callback; }
  remove() { this.removed = true; }
}
const doc = { createElement(tag) { return new Element(tag); } };
const conflict = (kind = "favs", key = "展示A") =>
  ({ kind, key, reason: "explicit_deletion_conflict" });
const report = review => ({ status: review.length ? "needs_review" : "prepared", review });
function elements(root, tag) {
  return [root, ...root.children.flatMap(child => elements(child, tag))]
    .filter(element => element.tag === tag);
}
const fav = { title: "A", museum: "M", dates: "", url: "" };
const entry = (value, deleted = false) => ({ value, deleted, revision: 1 });
function storage(favs = {}) {
  return { getItem(key) { return key === "taiwan_art_favs" ? JSON.stringify(favs) : "{}"; } };
}
test("ordinary sync renders absolutely no UI", () => {
  const container = new Element("main");
  const ui = createReview(container, report([]), doc);
  assert.equal(ui.rendered, false);
  assert.equal(container.children.length, 0);
  assert.deepEqual(ui.getDecisions(), []);
});
test("additive merge of separate saved exhibitions shows no UI", () => {
  const merged = plan(storage({ a: fav }),
    { revision: 1, favs: { b: entry(fav) }, visited: {} });
  const container = new Element("main");
  const ui = createReview(container, merged, doc);
  assert.equal(ui.rendered, false);
  assert.equal(container.children.length, 0);
});
test("identical saved exhibition shows no UI", () => {
  const merged = plan(storage({ a: fav }),
    { revision: 1, favs: { a: entry(fav) }, visited: {} });
  assert.equal(createReview(new Element("main"), merged, doc).rendered, false);
});
test("metadata differences do not prompt the user", () => {
  const merged = plan(storage({ a: fav }),
    { revision: 1, favs: { a: entry({ ...fav, museum: "N" }) }, visited: {} });
  assert.equal(createReview(new Element("main"), merged, doc).rendered, false);
});
test("explicit tombstone conflict shows exhibition-first prompt", () => {
  const container = new Element("main");
  const ui = createReview(container, report([conflict()]), doc);
  assert.equal(ui.rendered, true);
  const words = elements(container, "p").map(x => x.textContent).join(" ");
  assert.match(words, /「観たい」リストに残しますか/);
  assert.doesNotMatch(words, /サーバーを優先|この端末を優先/);
});
test("visited history has correct question and options", () => {
  const container = new Element("main");
  createReview(container, report([conflict("visited")]), doc);
  const words = elements(container, "p").map(x => x.textContent).join(" ");
  assert.match(words, /「観た」記録を残しますか/);
  assert.ok(elements(container, "option").some(x => x.textContent.includes("「観た」記録を外す")));
});
test("defaults to decide later", () => {
  const ui = createReview(new Element("main"), report([conflict()]), doc);
  assert.deepEqual(ui.getDecisions(), [{ kind: "favs", key: "展示A", choice: "decide_later" }]);
});
test("selection remains in-memory only", () => {
  const container = new Element("main");
  const ui = createReview(container, report([conflict()]), doc);
  const select = elements(container, "select")[0];
  select.value = "keep_saved";
  select.events.change();
  assert.equal(ui.getDecisions()[0].choice, "keep_saved");
});
test("remove selection is explicit and not executed", () => {
  const container = new Element("main");
  const ui = createReview(container, report([conflict()]), doc);
  const select = elements(container, "select")[0];
  select.value = "remove_from_list";
  select.events.change();
  assert.equal(ui.getDecisions()[0].choice, "remove_from_list");
});
test("invalid choice cannot change decision", () => {
  const container = new Element("main");
  const ui = createReview(container, report([conflict()]), doc);
  const select = elements(container, "select")[0];
  select.value = "keep_remote";
  select.events.change();
  assert.equal(ui.getDecisions()[0].choice, "decide_later");
});
test("exhibition key is inserted as text only", () => {
  const container = new Element("main");
  createReview(container, report([conflict("favs", "<img src=x>")]), doc);
  assert.equal(elements(container, "img").length, 0);
  assert.ok(elements(container, "p").some(x => x.textContent.includes("<img")));
});
test("same key in different lists is tracked separately", () => {
  const ui = createReview(new Element("main"),
    report([conflict("favs", "same"), conflict("visited", "same")]), doc);
  assert.equal(ui.getDecisions().length, 2);
});
test("rejects invalid conflict reason", () => {
  assert.throws(() => createReview(new Element("main"),
    report([{ ...conflict(), reason: "remote_only" }]), doc));
});
test("rejects duplicate conflict keys", () => {
  assert.throws(() => createReview(new Element("main"),
    report([conflict(), conflict()]), doc));
});
test("dispose removes only the review section", () => {
  const container = new Element("main");
  const ui = createReview(container, report([conflict()]), doc);
  ui.dispose();
  assert.equal(container.children[0].removed, true);
});
