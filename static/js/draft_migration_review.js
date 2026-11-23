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
    // Only explicit server deletions require a decision. Other differences
    // remain available to the coordinator, but do not interrupt the user.
    const items = report.rows.filter(row => row.status === "deleted_remotely").map(row => {
      const label = labels[row.kind];
      return { kind: row.kind, key: row.key, status: row.status,
        title: zh ? `要重新加入「${label}」嗎？` : `「${label}」に戻しますか？`,
        message: zh
          ? `之前移除的「${label}」還留在這裡。`
          : `以前「${label}」から外した展示が見つかりました。`,
        options: zh
          ? [{ id: "keep_deleted", label: "維持移除" },
             { id: "request_restore", label: `重新加入「${label}」` }]
          : [{ id: "keep_deleted", label: "戻さない" },
             { id: "request_restore", label: `「${label}」に戻す` }]
      };
    });
    return { status: "ready", mayWrite: false, items,
      summary: items.length
        ? (zh ? "請確認以下收藏。其他收藏不會變更。" : "次の登録だけ確認してください。ほかの登録は変更しません。")
        : (zh ? "不需要確認。收藏尚未變更。" : "確認が必要な登録はありません。登録はまだ変更していません。") };
  }
  return { preview, prepareBootstrap, explain };
});
