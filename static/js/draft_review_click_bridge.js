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
      ? require("./draft_legacy_snapshot.js") : root.TanDraftLegacySnapshot,
    typeof module === "object" && module.exports
      ? require("./draft_review_status_check.js") : root.TanDraftReviewStatusCheck
  );
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftReviewClickBridge = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function(ui, keep, legacy, statusCheck) {
  "use strict";
  function mount({ container, report, doc, serverState, localSnapshot, storage, request, fetchImpl }) {
    if (!container || !doc || !serverState ||
        !Number.isSafeInteger(serverState.revision) ||
        !localSnapshot || !storage || typeof request !== "function")
      throw new Error("Invalid review context");
    const review = ui.createReview(container, report, doc);
    if (!review.rendered) return { rendered: false, dispose: review.dispose };
    let busy = false;
    let disposed = false;
    let completed = false;
    let confirmationAttempted = false;
    const button = doc.createElement("button");
    button.textContent = "選択した展示を確認";
    button.setAttribute("type", "button");
    const status = doc.createElement("p");
    status.setAttribute("aria-live", "polite");
    status.setAttribute("aria-atomic", "true");
    const checkButton = doc.createElement("button");
    checkButton.textContent = "サーバーの登録状況を確認";
    checkButton.setAttribute("type", "button");
    checkButton.disabled = true;
    let attemptedDecision = null;
    let checking = false;
    const inspect = async () => {
      if (disposed || busy || checking || !confirmationAttempted || !attemptedDecision ||
          typeof fetchImpl !== "function") return;
      checking = true;
      checkButton.disabled = true;
      try {
        const result = await statusCheck.check({fetchImpl,kind:attemptedDecision.kind,
          key:attemptedDecision.key,expectedValue:attemptedDecision.value});
        if (disposed) return;
        status.textContent = result.status === "saved_on_server"
          ? "サーバーに登録が確認できました。ほかの展示は再読み込みして確認してください。"
          : result.status === "not_found"
            ? "サーバーにこの展示の登録は見つかりませんでした。保存成功とは判断できません。再送信せず、最新の状態で確認してください。"
          : result.status === "still_deleted"
            ? "サーバーには削除履歴が残っています。再送信せず、最新の状態で確認してください。"
            : result.status === "different_server_value"
              ? "サーバーには異なる登録内容があります。上書きせず、最新の状態で確認してください。"
              : "通信または応答の問題でサーバーの登録状況を確認できませんでした。保存の成否は不明です。再送信せず、時間をおいて再確認してください。";
      } catch (_) {
        if (!disposed) status.textContent = "サーバーの状態を確認できませんでした。再送信せず、時間をおいて再確認してください。";
      } finally {
        checking = false;
        if (!disposed) checkButton.disabled = false;
      }
    };
    checkButton.addEventListener("click", inspect);
    status.setAttribute("role", "status");
    const submit = async () => {
      if (disposed || busy || completed || confirmationAttempted) return;
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
          // Once confirmation starts, an interrupted response may hide a committed write.
          // Require a fresh review instead of allowing another submit from stale context.
          confirmationAttempted = true;
          attemptedDecision = {kind:decision.kind,key:decision.key,value:local[decision.key]};
          // Inspection remains unavailable while a confirmation request is in flight.
          const result = await keep.execute({
            decision, conflict: { ...conflict, itemRevision: entry.revision },
            localValue: local[decision.key],
            baseRevision: serverState.revision, request
          });
          if (disposed) return;
          if (result.status !== "submitted" || !result.state ||
              !Number.isSafeInteger(result.state.revision) ||
              result.state.revision <= serverState.revision) {
            status.textContent = "保存結果を確認できませんでした。最新の登録状況を再取得してから確認してください。";
            return;
          }
          // A successful write increments global revision. Do not send further
          // selections using the stale original revision.
          completed = true;
          status.textContent = "保存しました。ほかの展示は再読み込みして確認してください。";
          return;
        }
        status.textContent = "変更はありません。";
      } catch (_) {
        if (disposed) return;
        status.textContent = confirmationAttempted
          ? "保存された可能性があります。再送信せず、最新の登録状況を再取得して確認してください。"
          : "通信に失敗しました。状態を再取得して確認してください。";
      } finally {
        busy = false;
        if (!disposed && !completed && !confirmationAttempted) button.disabled = false;
        if (!disposed && confirmationAttempted && typeof fetchImpl === "function") checkButton.disabled = false;
      }
    };
    button.addEventListener("click", submit);
    container.appendChild(button);
    container.appendChild(status);
    if (typeof fetchImpl === "function") container.appendChild(checkButton);
    return { rendered: true, submit, inspect, dispose: () => {
      disposed = true;
      review.dispose();
      button.remove();
      status.remove();
      checkButton.remove();
    } };
  }
  return { mount };
});
