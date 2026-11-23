/* Exhibition-first deletion-conflict review, isolated draft.
 * No DOM for ordinary additive merges; no writes or API calls.
 */
(function(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftConflictUI = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function() {
  "use strict";
  const CHOICES = ["keep_saved", "remove_from_list", "decide_later"];
  function createReview(container, report, doc) {
    if (!container || !doc || typeof doc.createElement !== "function" ||
        !report || !["prepared", "needs_review"].includes(report.status) ||
        !Array.isArray(report.review)) throw new Error("Invalid merge report");
    const pending = report.review;
    const decisions = new Map();
    // Ordinary sync must not create even a hidden or empty review screen.
    if (pending.length === 0) return {
      rendered: false, getDecisions: () => [], dispose: () => {}
    };
    const section = doc.createElement("section");
    section.setAttribute("aria-label", "保存した展示の確認");
    const heading = doc.createElement("h2");
    heading.textContent = "保存した展示について確認";
    section.appendChild(heading);
    const description = doc.createElement("p");
    description.textContent = "以前リストから外された展示が、現在の記録にも残っています。どうしますか？";
    section.appendChild(description);
    for (const item of pending) {
      if (!item || !["favs", "visited"].includes(item.kind) ||
          typeof item.key !== "string" || !item.key ||
          item.reason !== "explicit_deletion_conflict")
        throw new Error("Invalid deletion conflict");
      const id = JSON.stringify([item.kind, item.key]);
      if (decisions.has(id)) throw new Error("Duplicate conflict");
      const wrapper = doc.createElement("div");
      const prompt = doc.createElement("p");
      prompt.textContent = item.key + (item.kind === "favs"
        ? "を「観たい」リストに残しますか？"
        : "の「観た」記録を残しますか？");
      wrapper.appendChild(prompt);
      const select = doc.createElement("select");
      select.setAttribute("aria-label", item.key + " の保存状態");
      const options = [
        ["decide_later", "あとで決める"],
        ["keep_saved", item.kind === "favs" ? "「観たい」に残す" : "「観た」記録を残す"],
        ["remove_from_list", item.kind === "favs" ? "「観たい」から外す（まだ反映されません）" : "「観た」記録を外す（まだ反映されません）"]
      ];
      for (const [value, label] of options) {
        const option = doc.createElement("option");
        option.value = value;
        option.textContent = label;
        select.appendChild(option);
      }
      decisions.set(id, "decide_later");
      select.addEventListener("change", () => {
        if (CHOICES.includes(select.value)) decisions.set(id, select.value);
      });
      wrapper.appendChild(select);
      section.appendChild(wrapper);
    }
    const note = doc.createElement("p");
    note.textContent = "「残す」を選んで確認すると、その展示だけ登録します。「外す」と「あとで決める」は記録を変更しません。";
    section.appendChild(note);
    container.appendChild(section);
    return {
      rendered: true,
      getDecisions: () => Array.from(decisions, ([id, choice]) => {
        const [kind, key] = JSON.parse(id);
        return { kind, key, choice };
      }),
      dispose: () => section.remove()
    };
  }
  return { createReview };
});
