// Unit tests for the *actual* key-migration IIFE in templates/index.html,
// extracted verbatim from the real file (same string-slice technique as
// other *_actual_template tests) so these exercise the real logic without
// a browser. Mirrors docs/security/FOUR_PAGE_WRITER_MIGRATION_MATRIX_DRAFT.md's
// two concrete requirements for migrateStore: never silently drop a
// colliding old/new key, and never mark migration complete after a
// partial failure.
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path");

const raw = fs.readFileSync(path.resolve(__dirname, "../templates/index.html"), "utf8");
const begin = raw.indexOf("  // Migrate old localStorage keys");
const marker = "localStorage.setItem(MIGRATED_KEY, '1');";
const markerEnd = raw.indexOf(marker, begin);
if (begin < 0 || markerEnd < 0) throw Error("real migration IIFE not found in templates/index.html");
const end = raw.indexOf("})();", markerEnd);
if (end < 0) throw Error("real migration IIFE closing not found in templates/index.html");
const snippet = raw.slice(begin, end + "})();".length);

function run(initial, nameToId) {
  const store = {...initial};
  const localStorage = {
    getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
    setItem: (k, v) => { store[k] = v; },
  };
  const body = snippet.replace(
    "{{ museum_name_to_id_json | safe }}",
    JSON.stringify(nameToId)
  );
  const fn = new Function("localStorage", body);
  fn(localStorage);
  return store;
}

test("a plain museum-name key is renamed to the museum id, migration marked complete", () => {
  const store = run(
    {taiwan_art_favs: JSON.stringify({"台北市立美術館__展覽A": {title: "展覽A"}})},
    {"台北市立美術館": "taipeifam"}
  );
  const favs = JSON.parse(store.taiwan_art_favs);
  assert.deepEqual(Object.keys(favs), ["taipeifam__展覽A"]);
  assert.equal(store.taiwan_art_keys_migrated_v1, "1");
});

test("a key already in new (short, ASCII id) format is left untouched", () => {
  const store = run(
    {taiwan_art_favs: JSON.stringify({"taipeifam__展覽A": {title: "展覽A"}})},
    {"台北市立美術館": "taipeifam"}
  );
  const favs = JSON.parse(store.taiwan_art_favs);
  assert.deepEqual(Object.keys(favs), ["taipeifam__展覽A"]);
});

test("an unresolvable museum name is left under its original key, not dropped", () => {
  const store = run(
    {taiwan_art_favs: JSON.stringify({"不明的美術館__展覽A": {title: "展覽A"}})},
    {"台北市立美術館": "taipeifam"}
  );
  const favs = JSON.parse(store.taiwan_art_favs);
  assert.deepEqual(Object.keys(favs), ["不明的美術館__展覽A"]);
});

test("two old keys colliding on the same new key both survive: first migrates, second keeps its old key", () => {
  // Two historical name spellings for the same museum, same exhibition
  // title -- a real collision class, per the matrix's own warning.
  const store = run(
    {
      taiwan_art_favs: JSON.stringify({
        "台北市立美術館__展覽A": {title: "展覽A", savedBy: "first"},
        "北美館__展覽A": {title: "展覽A", savedBy: "second"},
      }),
    },
    {"台北市立美術館": "taipeifam", "北美館": "taipeifam"}
  );
  const favs = JSON.parse(store.taiwan_art_favs);
  // Neither entry is lost: one migrated to the new key, the other stayed
  // under its own old key rather than being silently overwritten.
  assert.equal(Object.keys(favs).length, 2);
  assert.equal(favs["taipeifam__展覽A"].savedBy, "first");
  assert.equal(favs["北美館__展覽A"].savedBy, "second");
  assert.equal(store.taiwan_art_keys_migrated_v1, "1");
});

test("malformed JSON in one store does not mark migration complete, so it retries next load", () => {
  const store = run(
    {
      taiwan_art_favs: "{not valid json",
      taiwan_art_visited: JSON.stringify({"台北市立美術館__展覽A": "2026-01-01"}),
    },
    {"台北市立美術館": "taipeifam"}
  );
  // The malformed store is left exactly as it was (never overwritten with
  // an empty/partial result), and the migrated flag is never set, so a
  // future page load will retry both stores rather than permanently
  // skipping the one that failed.
  assert.equal(store.taiwan_art_favs, "{not valid json");
  assert.equal(store.taiwan_art_keys_migrated_v1, undefined);
});

test("already-migrated sessions never run again", () => {
  const store = run(
    {
      taiwan_art_keys_migrated_v1: "1",
      taiwan_art_favs: JSON.stringify({"台北市立美術館__展覽A": {title: "展覽A"}}),
    },
    {"台北市立美術館": "taipeifam"}
  );
  const favs = JSON.parse(store.taiwan_art_favs);
  assert.deepEqual(Object.keys(favs), ["台北市立美術館__展覽A"]); // untouched
});
