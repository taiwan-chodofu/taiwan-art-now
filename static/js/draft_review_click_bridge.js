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
    const review = ui.createReview(container, report, doc, localSnapshot);
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
    const nextButton = doc.createElement("button");
    nextButton.textContent = "残りの展示を確認";
    nextButton.setAttribute("type", "button");
    let nextReview = null;
    let openingNext = false;
    const remainingList = doc.createElement("div");
    remainingList.setAttribute("aria-label", "確認が必要な展示");
    const checkButton = doc.createElement("button");
    checkButton.textContent = "登録状況をもう一度確認";
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
          ? "この展示は登録されています。ほかの展示も確認してください。"
          : result.status === "not_found"
            ? "この展示の登録は確認できませんでした。登録状況をもう一度確認してください。"
          : result.status === "still_deleted"
            ? "この展示は以前リストから外されています。登録するかどうか、もう一度確認してください。"
            : result.status === "different_server_value"
              ? "この展示の登録内容がほかの端末と異なります。内容を確認してください。"
              : "登録状況を確認できませんでした。少し待ってから、もう一度確認してください。";
      } catch (_) {
        if (!disposed) status.textContent = "登録状況を確認できませんでした。少し待ってから、もう一度確認してください。";
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
            status.textContent = "登録できたか確認できませんでした。「登録状況をもう一度確認」を押してください。";
            return;
          }
          // A successful write increments global revision. Do not send further
          // selections using the stale original revision.
          completed = true;
          const others = report.review.filter(item =>
            item.kind !== decision.kind || item.key !== decision.key);
          status.textContent = others.length
            ? "この展示を登録しました。あと" + others.length + "件、確認が必要な展示があります。"
            : "この展示を登録しました。";
          if (others.length && typeof fetchImpl === "function") {
            const latest = await statusCheck.readState({fetchImpl});
            if (disposed) return;
            const confirmed = latest.status === "ready" &&
              latest.state.revision >= result.state.revision &&
              latest.state[decision.kind] &&
              latest.state[decision.kind][decision.key] &&
              !latest.state[decision.kind][decision.key].deleted &&
              JSON.stringify(latest.state[decision.kind][decision.key].value) ===
                JSON.stringify(local[decision.key]);
            if (confirmed) {
              const pending = others.filter(item => {
                const entry = latest.state[item.kind] && latest.state[item.kind][item.key];
                return entry && entry.deleted;
              });
              status.textContent = pending.length
                ? "この展示を登録しました。あと" + pending.length + "件、確認が必要な展示があります。"
                : "この展示を登録しました。ほかに確認が必要な展示はありません。";
              if (pending.length) {
                nextReview = {report: {status: "needs_review", review: pending}, serverState: latest.state};
                nextButton.disabled = false;
              }
              for (const item of pending) {
                const label = doc.createElement("p");
                const saved = localSnapshot[item.kind] && localSnapshot[item.kind][item.key];
                const title = saved && typeof saved.title === "string" && saved.title.trim()
                  ? saved.title.trim() : item.key;
                label.textContent = title + (item.kind === "favs" ? "（観たい）" : "（観た）");
                remainingList.appendChild(label);
              }
            } else {
              status.textContent = "登録状況を確認できませんでした。ほかの展示へ進まず、登録状況をもう一度確認してください。";
            }
          }
          return;
        }
        const deferred = review.getDecisions();
        status.textContent = deferred.some(d => d.choice === "remove_from_list")
          ? "「リストから外す」はまだ反映されていません。登録内容は変更されていません。"
          : "登録内容は変更されていません。あとで確認できます。";
      } catch (_) {
        if (disposed) return;
        status.textContent = confirmationAttempted
          ? "登録できたか確認できませんでした。「登録状況をもう一度確認」を押してください。"
          : "通信がうまくいきませんでした。もう一度確認してください。";
      } finally {
        busy = false;
        if (!disposed && !completed && !confirmationAttempted) button.disabled = false;
        if (!disposed && confirmationAttempted && typeof fetchImpl === "function") checkButton.disabled = false;
      }
    };
    nextButton.disabled = true;
    nextButton.addEventListener("click", async () => {
      if (disposed || busy || openingNext || !completed || !nextReview) return;
      openingNext = true;
      nextButton.disabled = true;
      // A second device may have changed the list since the previous GET.
      // Read again before creating a new confirmation screen; never write here.
      let fresh;
      try { fresh = await statusCheck.readState({fetchImpl}); }
      catch (_) { fresh = {status:"unavailable"}; }
      if (disposed) return;
      if (fresh.status !== "ready") {
        status.textContent = "ほかの展示を確認できませんでした。もう一度お試しください。";
        openingNext = false;
        nextButton.disabled = false;
        return;
      }
      const localNow = legacy.read(storage);
      if (localNow.status !== "ready" ||
          JSON.stringify(localNow.snapshot) !== JSON.stringify(localSnapshot)) {
        status.textContent = "この端末の記録が変わりました。最新の内容を確認してください。";
        nextReview = null;
        return;
      }
      const pending = nextReview.report.review.filter(item => {
        const entry = fresh.state[item.kind] && fresh.state[item.kind][item.key];
        return entry && entry.deleted && localSnapshot[item.kind] &&
          Object.prototype.hasOwnProperty.call(localSnapshot[item.kind], item.key);
      });
      if (!pending.length) {
        status.textContent = "確認が必要な展示はありません。";
        nextReview = null;
        return;
      }
      const next = {report: {status:"needs_review",review:pending}, serverState:fresh.state};
      dispose();
      mount({container, report: next.report, doc, serverState: next.serverState,
        localSnapshot, storage, request, fetchImpl});
    });
    button.addEventListener("click", submit);
    container.appendChild(button);
    container.appendChild(status);
    container.appendChild(remainingList);
    container.appendChild(nextButton);
    if (typeof fetchImpl === "function") container.appendChild(checkButton);
    function dispose() {
      disposed = true;
      review.dispose();
      button.remove();
      status.remove();
      remainingList.remove();
      nextButton.remove();
      checkButton.remove();
    }
    return { rendered: true, submit, inspect, dispose };
  }
  return { mount };
});
