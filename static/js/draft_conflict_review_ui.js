/* Isolated conflict review UI. NOT loaded by production templates.
 * All decisions are a local draft, never persisted or sent to an API.
 * No record values or identities are included in DOM attributes.
 */
(function(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftConflictUI = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function() {
  "use strict";
  const choices = ["keep_local", "keep_remote", "decide_later"];
  const statusLabels = {
    same: "一致", local_only: "この端末のみ", remote_only: "サーバーのみ",
    different: "内容が異なる", deleted_remotely: "サーバーで削除済み",
    remote_tombstone: "削除履歴のみ"
  };
  function createReview(container, report, doc) {
    if (!container || !doc || typeof doc.createElement !== "function" ||
        !report || report.status !== "ready" || !Array.isArray(report.rows))
      throw new Error("Valid review report and DOM required");
    const decisions = new Map();
    const root = doc.createElement("section");
    root.setAttribute("aria-label", "同期内容の確認");
    const heading = doc.createElement("h2");
    heading.textContent = "保存した展示の確認（試作）";
    root.appendChild(heading);
    const description = doc.createElement("p");
    description.textContent = "ここでの選択は保存されません。現在の記録は変更されません。";
    root.appendChild(description);
    const pending = report.rows.filter(row =>
      ["remote_only", "different", "deleted_remotely"].includes(row.status));
    for (const row of pending) {
      if (!["favs", "visited"].includes(row.kind) ||
          typeof row.key !== "string" ||
          !Object.prototype.hasOwnProperty.call(statusLabels, row.status))
        throw new Error("Invalid review row");
      const id = JSON.stringify([row.kind, row.key]);
      const item = doc.createElement("div");
      const label = doc.createElement("p");
      // textContent prevents exhibition keys being interpreted as markup.
      label.textContent = (row.kind === "favs" ? "観たい" : "観た") +
        " / " + row.key + " — " + statusLabels[row.status];
      item.appendChild(label);
      const select = doc.createElement("select");
      select.setAttribute("aria-label", row.key + " の扱い");
      for (const [value, caption] of [
        ["decide_later", "あとで決める"],
        ["keep_local", "この端末の記録を優先（未実行）"],
        ["keep_remote", "サーバーの記録を優先（未実行）"]
      ]) {
        const option = doc.createElement("option");
        option.value = value;
        option.textContent = caption;
        select.appendChild(option);
      }
      decisions.set(id, "decide_later");
      select.addEventListener("change", () => {
        if (!choices.includes(select.value)) return;
        decisions.set(id, select.value);
      });
      item.appendChild(select);
      root.appendChild(item);
    }
    const note = doc.createElement("p");
    note.textContent = pending.length
      ? pending.length + "件の確認事項があります。選択しても同期は実行されません。"
      : "確認が必要な競合はありません。同期は実行されません。";
    root.appendChild(note);
    container.appendChild(root);
    return {
      getDecisions: () => Array.from(decisions, ([id, choice]) => {
        const [kind, key] = JSON.parse(id);
        return { kind, key, choice };
      }),
      dispose: () => root.remove()
    };
  }
  return { createReview };
});
