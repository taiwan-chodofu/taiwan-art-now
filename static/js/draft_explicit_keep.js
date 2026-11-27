/* Draft-only explicit keep action. Never invoked during ordinary sync.
 * Requires caller to supply a reviewed decision from the UI and exact
 * tombstone revisions. No localStorage mutation.
 */
(function(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftExplicitKeep = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function() {
  "use strict";
  async function execute({ decision, conflict, localValue, baseRevision, request }) {
    if (!decision || !conflict ||
        decision.choice !== "keep_saved" ||
        !["favs", "visited"].includes(decision.kind) ||
        decision.kind !== conflict.kind || decision.key !== conflict.key ||
        conflict.reason !== "explicit_deletion_conflict" ||
        typeof decision.key !== "string" || !decision.key ||
        !Number.isSafeInteger(baseRevision) || baseRevision < 1 ||
        !Number.isSafeInteger(conflict.itemRevision) ||
        conflict.itemRevision < 1 || conflict.itemRevision > baseRevision ||
        localValue === null || localValue === undefined ||
        typeof request !== "function")
      return { status: "not_authorized" };
    // Only a caller triggered by a user click may call execute; a JavaScript
    // function cannot attest a genuine click. No automatic call from sync.
    const issued = await request("/api/private-subscribers/v2/review/keep/issue", {
      choice: "keep_saved", kind: decision.kind, key: decision.key,
      base_revision: baseRevision,
      reviewed_item_revision: conflict.itemRevision, local_value: localValue
    });
    if (!issued || typeof issued.token !== "string" || !issued.token)
      return { status: "issue_failed" };
    const result = await request("/api/private-subscribers/v2/review/keep/consume", {
      token: issued.token, local_value: localValue
    });
    return { status: "submitted", state: result };
  }
  return { execute };
});
