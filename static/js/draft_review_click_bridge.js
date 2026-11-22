/* Draft-only click-to-confirm bridge. No production mounting or auto-sync.
 * A selection alone NEVER sends a request. Only explicit button click does.
 */
(function(root, factory) {
  const api = factory(
    typeof module === "object" && module.exports
      ? require("./draft_conflict_review_ui.js") : root.TanDraftConflictUI,
    typeof module === "object" && module.exports
      ? require("./draft_explicit_keep.js") : root.TanDraftExplicitKeep,
    typeof module === "object" && module.exports
      ? require("./draft_legacy_snapshot.js") : root.TanDraftLegacySnapshot
  );
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftReviewClickBridge = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function(ui, keep, legacy) {
  "use strict";
  function mount({ container, report, doc, serverState, localSnapshot, storage, request }) {
    if (!container || !doc || !serverState ||
        !Number.isSafeInteger(serverState.revision) ||
        !localSnapshot || !storage || typeof request !== "function")
      throw new Error("Invalid review context");
    const review = ui.createReview(container, report, doc);
    if (!review.rendered) return { rendered: false, dispose: review.dispose };
    let busy = false;
    let disposed = false;
    const button = doc.createElement("button");
    button.textContent = "選択した展示を確認";
    button.setAttribute("type", "button");
    const status = doc.createElement("p");
    status.setAttribute("role", "status");
    const submit = async () => {
      if (disposed || busy) return;
      busy = true;
      button.disabled = true;
      try {
        const current = legacy.read(storage);
        if (current.status !== "ready" ||
            JSON.stringify(current.snapshot) !== JSON.stringify(localSnapshot)) {
          status.textContent = "この端末の記録が変わりました。再確認してください。";
          return;
        }
        const decisions = review.getDecisions().filter(d => d.choice === "keep_saved");
        // Only affirmative keep selections require server confirmation.
        // remove/defer stay pending, without local or remote changes.
        for (const decision of decisions) {
          const conflict = report.review.find(item =>
            item.kind === decision.kind && item.key === decision.key);
          const entry = serverState[decision.kind] &&
            serverState[decision.kind][decision.key];
          const local = localSnapshot[decision.kind];
          if (!entry || !entry.deleted || !local ||
              !Object.prototype.hasOwnProperty.call(local, decision.key)) {
            status.textContent = "記録が変わりました。再読み込みして確認してください。";
            return;
          }
          const result = await keep.execute({
            decision, conflict: { ...conflict, itemRevision: entry.revision },
            localValue: local[decision.key],
            baseRevision: serverState.revision, request
          });
          if (result.status !== "submitted" || !result.state ||
              !Number.isSafeInteger(result.state.revision) ||
              result.state.revision <= serverState.revision) {
            status.textContent = "保存できませんでした。再確認してください。";
            return;
          }
          // A successful write increments global revision. Do not send further
          // selections using the stale original revision.
          status.textContent = "保存しました。ほかの展示は再読み込みして確認してください。";
          return;
        }
        status.textContent = "変更はありません。";
      } catch (_) {
        status.textContent = "通信に失敗しました。状態を再取得して確認してください。";
      } finally {
        busy = false;
        if (!disposed) button.disabled = false;
      }
    };
    button.addEventListener("click", submit);
    container.appendChild(button);
    container.appendChild(status);
    return { rendered: true, submit, dispose: () => {
      disposed = true;
      review.dispose();
      button.remove();
      status.remove();
    } };
  }
  return { mount };
});
