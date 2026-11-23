/* Draft read-only migration and conflict-review model; no storage/network writes.
 * A legacy absence NEVER means deletion. Server tombstones are authoritative
 * until a human explicitly resolves them through a separate authenticated flow.
 */
(function(root, factory) {
  const api = factory(
    typeof module === "object" && module.exports
      ? require("./draft_legacy_snapshot.js") : root.TanDraftLegacySnapshot,
    typeof module === "object" && module.exports
      ? require("./draft_versioned_sync.js") : root.TanDraftSync
  );
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TanDraftMigrationReview = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function(legacy, sync) {
  "use strict";
  const KINDS = ["favs", "visited"];
  const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
  function preview(storage, serverState) {
    const parsed = legacy.read(storage);
    if (parsed.status !== "ready") return { status: parsed.status, kind: parsed.kind };
    // The sync planner validates the server shape and makes no writes.
    let plan;
    try { plan = sync.plan(parsed.snapshot, serverState); }
    catch (_) { return { status: "invalid_server" }; }
    const rows = [];
    for (const kind of KINDS) {
      const local = parsed.snapshot[kind];
      const remote = serverState[kind];
      const keys = new Set([...Object.keys(local), ...Object.keys(remote)]);
      for (const key of keys) {
        const localPresent = own(local, key);
        const record = own(remote, key) ? remote[key] : undefined;
        const remotePresent = !!record && !record.deleted;
        let status;
        if (record && record.deleted && localPresent) status = "deleted_remotely";
        else if (record && record.deleted) status = "remote_tombstone";
        else if (localPresent && !record) status = "local_only";
        else if (!localPresent && remotePresent) status = "remote_only";
        else if (localPresent && remotePresent &&
          JSON.stringify(local[key]) === JSON.stringify(record.value)) status = "same";
        else status = "different";
        rows.push(Object.freeze({
          kind, key, status, localPresent, remotePresent,
          // No values in review summary: caller must explicitly request
          // details from already-authorized local/server snapshots.
          remoteRevision: record ? record.revision : null
        }));
      }
    }
    return { status: "ready", revision: serverState.revision,
      safeToWrite: plan.safeToWrite,
      counts: rows.reduce((acc, row) => {
        acc[row.status] = (acc[row.status] || 0) + 1;
        return acc;
      }, Object.create(null)),
      rows };
  }
  function prepareBootstrap(storage, serverState) {
    const report = preview(storage, serverState);
    if (report.status !== "ready") return report;
    // Migration may only be prepared against a genuinely empty, revision-0
    // state. Existing server history must use explicit conflict review.
    if (serverState.revision !== 0 ||
        KINDS.some(kind => Object.keys(serverState[kind]).length !== 0))
      return { status: "requires_review", counts: report.counts };
    const parsed = legacy.read(storage);
    if (parsed.status !== "ready") return { status: parsed.status, kind: parsed.kind };
    const changes = { favs: Object.create(null), visited: Object.create(null) };
    for (const kind of KINDS) {
      for (const [key, value] of Object.entries(parsed.snapshot[kind]))
        changes[kind][key] = { set: value };
    }
    return { status: "prepared", base_revision: 0, changes };
  }
  function explain(report, lang = "ja") {
    if (!report || report.status !== "ready" || !Array.isArray(report.rows))
      return { status: "invalid_review", mayWrite: false, items: [] };
    const zh = lang === "zh";
    const labels = zh ? { favs: "想去", visited: "看過" }
      : { favs: "観たい", visited: "観た" };
    const items = report.rows.filter(row => row.status !== "same").map(row => {
      const subject = `「${row.key}」の「${labels[row.kind]}」`;
      const chineseSubject = `「${row.key}」的「${labels[row.kind]}」`;
      const messages = zh ? {
        local_only: `${chineseSubject}只存在這個裝置。確認後才能決定是否匯入。`,
        remote_only: `${chineseSubject}已儲存在伺服器；此裝置沒有資料不代表刪除。`,
        deleted_remotely: `${chineseSubject}已在伺服器刪除。請確認是否恢復；不會自動恢復。`,
        remote_tombstone: `${chineseSubject}已在伺服器刪除。保持刪除狀態。`,
        different: `${chineseSubject}在裝置與伺服器的內容不同。請先確認差異。`
      } : {
        local_only: `${subject}はこの端末だけにあります。内容を確認してから移行を判断してください。`,
        remote_only: `${subject}はサーバーに保存されています。この端末になくても削除しません。`,
        deleted_remotely: `${subject}はサーバーで削除済みです。復元するか確認してください。自動復元はしません。`,
        remote_tombstone: `${subject}はサーバーで削除済みです。削除状態を保持します。`,
        different: `${subject}は端末とサーバーで登録内容が異なります。差異を確認してください。`
      };
      return { kind: row.kind, key: row.key, status: row.status,
        message: messages[row.status] || (zh ? "請確認收藏狀態。" : "登録状況を確認してください。") };
    });
    return { status: "ready", mayWrite: false, items,
      summary: zh ? "這只是確認清單，尚未修改任何收藏。"
        : "これは確認用の一覧です。登録の変更や移行はまだ行っていません。" };
  }
  return { preview, prepareBootstrap, explain };
});
