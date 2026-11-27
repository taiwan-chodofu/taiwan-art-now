# Taiwan Art Now 端末間同期 — Claude Code引き継ぎ
更新日 2026-11-25。コード確認基準 3953c77b9f6df1a526db748144dcf189234aabc9。

## 1. 目的と引き継ぎ時点
ユーザーは時間・トークン消費を減らして開発を完成させたい。ChatGPTによる小変更ごとのコミット、全CI実行、短い進捗報告の反復を改善したいという要望がある。
Claude Codeが次の実装担当。今回の引き継ぎ文書以後、ChatGPTが並行実装する予定はない。リモートが進んでいたら新しい変更を優先し、既存の作業を上書きしない。

- Repository https://github.com/taiwan-chodofu/taiwan-art-now
- Draft PR https://github.com/taiwan-chodofu/taiwan-art-now/pull/87
- Branch feat/private-subscriber-storage-adapter-83
- 関連 Issue #83
- 確認済みCI https://github.com/taiwan-chodofu/taiwan-art-now/actions/runs/45581227251
- 上記コードコミットの5ジョブすべて成功。Node 422件。
- ローカルPython全探索は過去の実行で336件、DB専用18件skip。直近コードの全Python検証はCIを参照。
- マージ・本番デプロイ・本番データ変更は未承認。明示的承認が必要。
- 「完成度60％」は会話内の粗い推測。工程別の受入条件から再評価すること。

この文書は実装開始の地図。AGENTS.md、CLAUDE.md、DATA_QUALITY_RULES.mdと併読する。
CURRENT.mdは追記式の履歴で、冒頭に古い2026-11-22の状態が残る。古い未実施記載と現在のコードを照合する。
docs/securityの古い「ルート未登録」「未実施」記載も、隔離テストでの登録・実施と本番登録を区別して読む。

## 2. 必須の振る舞い
- favs（観たい）とvisited（観た）は独立。観たを付けても観たいを消さない。
- 古いスナップショットに項目がないことを削除意図と解釈しない。
- 明示的削除はrevision付きtombstone。通常のsetで復活させない。
- 両端末の登録は原則保持する。明示的な削除と登録が衝突したときに具体的な項目・操作を示す。
- POSTの応答消失、5xx、検証不能を未保存と決めつけない。曖昧な保存を自動再送しない。
- GETなど安全な確認は自動化し、不要な再読み込みやユーザー判断を減らす。
- 一つの画面で旧保存ハンドラーと新ハンドラーを同時に動かさない。
- UI表示、履歴、分析イベントは保存確認と整合させる。
- 日本語・台湾華語は具体的な次の操作が伝わる文言にする。「端末を優先」「登録状況を更新」だけでは伝わらない。
- 既存の展示・メタデータ・URL・通知連携を維持する。無関係なデータ更新を混ぜない。

## 3. 現在の構成
### サーバー
| ファイル | 役割 |
| --- | --- |
| versioned_subscriber_sync.py | 状態検証、revision付き変更、独立コレクション |
| versioned_subscriber_store.py | PostgreSQL CAS。初期行のない場合もadvisory lockで直列化 |
| versioned_subscriber_api_routes.py | GET state、POST changes。セッション所有者の検証と変更を同一transactionで実施 |
| browser_session*.py / browser_cookie_security.py | cookie、期限・失効、同一origin検証 |
| subscriber_review_confirmation.py | 所有者・値・削除revisionに結びつく一回限りの復元token |
| subscriber_review_api_routes.py | 復元tokenのissueとconsume |
| isolated_versioned_staging_app.py | loopback HTTPS限定の隔離Flask factory。read_only時はPOSTを停止 |
| tests/fixtures/serve_disposable_sync.py | CI専用HTTPSサーバー、合成所有者とcookie、実テンプレート用ルート |

状態はglobal revisionとfavs/visitedのmapを持つ。各項目はvalue、deleted、revisionを持つ。
GET /api/private-subscribers/v2/state
POST /api/private-subscribers/v2/changes
POST /api/private-subscribers/v2/review/keep/issue
POST /api/private-subscribers/v2/review/keep/consume

changesはbase_revisionとfavs/visitedの変更map。通常のchangesはtombstoneへのsetを拒否する。
復元は確認済みのrevisionと項目revisionをissueし、consumeで再検証・更新する。
本番app.pyにversioned/review blueprintを登録していない。隔離factoryは4ルートを登録済み。
本PRには以前のprivate subscriber、webhook、所有権改善も含まれるため、同期JSだけを見てPR全体を安全と判断しない。

### ブラウザ共通
| ファイル | 現在の役割と制約 |
| --- | --- |
| draft_versioned_sync.js | 状態検証、同一JSON比較、認証GET、初期同期。POST後GET検証あり |
| draft_authenticated_state.js | 上記readerを公開する薄い互換wrapper |
| draft_authenticated_writer.js | fresh GET→revision照合→通常POST→GET検証。dispose中断のisActive対応 |
| draft_explicit_keep.js / draft_explicit_server_restore.js | issue/consume復元。consume前のdisposeを検査 |
| draft_server_page_action.js | busy、callback、通常保存と復元の共通処理 |
| draft_server_button_bridge.js | revision付きボタン。確定/曖昧/競合後にGETで再描画 |
| draft_staging_page.js | 全ボタンの状態・ライフサイクル。古い応答排除、revision下限、listener破棄 |
| draft_additive_merge.js / draft_additive_retry.js | 既存登録を残す追加移行。409だけ最大1回再計画。曖昧POSTは再送しない |
| draft_legacy_snapshot.js | favs metadata、visited ISO文字列/metadataの旧形式を検証 |
| draft_legacy_writer.js / draft_page_action.js / draft_page_controller.js | 旧localStorage向けの協調lock。旧PWAはこのlockを無視できる |
| draft_migration_review.js / draft_simple_review_ui.js | 削除衝突のレビュー |
| draft_post_save_verify.js / draft_save_review_flow.js | 保存後の旧local変更に対する表示・再確認 |
| static/sw.js | private APIをキャッシュ経路から外す |

認証GETは現在のService Workerにnetwork-only capabilityを問い合わせる。
応答しない旧workerではworker_update_required。GET中にcontrollerが変わった場合も結果を捨てる。
no-storeヘッダーだけでは旧workerのキャッシュ応答を区別できないため追加した。
publicページの従来のoffline方針は維持。実機iOSのworker更新手順は未検証。

曖昧POST後のGETでglobal revisionが元のCASより進んだ場合だけ古い操作を再利用しない形で画面を更新する。
同じrevisionなら遅延したPOSTがまだ反映され得るためロック維持。
表示は「現在登録されている」。元のクリックが成功したと断定しない。
onlineとpersisted pageshowで読み取り更新。通知をまとめ、mutation中は開始しない。
persisted pagehideでは維持、通常pagehideでdispose。実bfcacheの全端末検証は未完了。

## 4. 画面別の到達点
### 展示詳細
templates/exhibition_detail_page.html のTAN_ISOLATED_DETAIL_SYNC。
隔離fixtureだけが有効化。server render時に旧toggleFav/toggleVisitedを省略する。
初回GET完了までdisabled。保存・削除・復元・応答消失後の表示を実テンプレート＋DBで検証。
復元ボタンは「『観たい』に戻す」/「重新加入『想看』」。この明示クリックを復元意図として扱う。
メタデータにtojsonを使用。通常render側は従来経路。
実験画面での日本語・台湾華語を優先して実装した。既存英語ロケールとの整合は再確認が必要。

### 周辺
templates/nearby.html のTAN_ISOLATED_NEARBY_SYNC。
複数展示の全操作を一つのlifecycleで管理。global revision更新を全ボタンに反映する。
spanから実験モードのbuttonへ変更、旧toggleActionを省略。
保存A→観たB→削除A→復元A、他タブ変更後の再接続GETを実DBで検証。
空一覧はcontrollerを作らない。

### Discover — 次の最優先
templates/discover.htmlはまだlocalStorageのflowを選択している。
draft_discover_flow.jsにfetchImplを渡すと認証APIを使う経路が追加された。
- existing active項目は上書きしない。カードだけ進め、undoはカードだけ戻す。
- 新規保存のitem revisionを記録し、undoでrevisionとvalue両方を照合する。
- same-valueを別端末が再登録していても古いundoで消さない。
- unknown writeはuncertainフラグを立て、以後swipe/skip/undoを停止する。
- 成功statusは互換性のためwritten_under_cooperative_lockという旧名を返す。サーバー経路でもこの文字列なので誤解に注意。
- clearHistoryはuncertainを解消しない。復旧APIとdisposeは未実装。
- サーバーtombstoneへの復元UIは未接続。
- createdRevisionsはkind/keyごとのmap。カード再出現や複数履歴が同じkeyを持つ場合の所有関係は改めて評価する。
- normalizeKeyをcallerから受け取る。raw stable_keyと既存正規化keyの対応を決める前に本番適用しない。
- 初期visited/favs、フィルター、deck/source order、restart、undo、onErrorの表示が旧localStorage前提。
- reader/writerをscript順序に追加するだけでは完成しない。

関連テンプレート関数はcommitSwipe、undo、advanceDiscover、failDiscoverと末尾のmode/filter処理。
テストはtest_draft_discover_flow.cjs、draft_discover_actual_template.spec.cjs、draft_discover_additional_browser.spec.cjs。
実DBテストはdisposable_sync_browser.spec.cjsのDiscover server flow。これはflowを隔離HTMLへ注入したもので、Discover全体の接続を証明していない。

### ホーム
templates/index.htmlは未接続。重点入口はtoggleAction、markVisitedFromMylist、removeFromMylist、migrateStore。
一覧・マイリスト・フィルター・通知syncと一回限りkey移行を一緒に追う。
全体map書き戻し、移行済みflag、表示キー衝突が要注意。
docs/security/FOUR_PAGE_WRITER_MIGRATION_MATRIX_DRAFT.mdを地図として使う。

## 5. 根本的な未解決事項
1. ID整合。app.pyはmuseum IDとtitle由来でstable_keyを生成する。旧JSは非許可文字をunderscoreに置換する。詳細/周辺の隔離経路は渡されたkeyをそのまま使う。現テストの単純な合成keyでは差異を検出できない。実形式の句読点、空白、日本語、英語、重複題名、改題を含む合成fixtureで衝突・対応・移行を設計する。
2. 旧タブのlocalStorage全体上書きはまだ可能。新DBに保存済みの登録は保護できても、旧端末だけにある未移行登録は消え得る。Web Locks、checkpoint、workerの更新案内だけでは解決しない。
3. metadata差異を勝手に上書きしない現方針と、改題/URL更新の扱いを整理する。sameJsonを利用し、JSONBのkey順序の違いで誤判定しない。
4. 認証主体が変わる場合の画面キャッシュ・履歴・revision基準の破棄を評価する。既存セッション失効テストはあるが、アカウント切替全UIを保証していない。
5. 個別POSTとreadbackは二段階。同じrevisionで内容が一致しても元のrequestの一意識別は実装されていない。曖昧保存を勝手にリトライする変更は避ける。
6. 複数コレクションを共有するUI、戻る/進む、offline/online中の未完了POST、再描画中のクリックとdisposeを検証する。
7. 独立した長期バックアップ、暗号鍵回復、保持期間、復旧時間、運用担当、rollout停止手順は未整備。
8. 実機のインストール済み旧iOS PWAと別端末を同時使用する検証は未実施。提供環境でできない場合は具体的な検証手順と期待結果を完成させて残す。

既存の安全性文書
- docs/security/STAGING_INTEGRATION_EXIT_CRITERIA.md
- docs/security/EXHIBITION_BACKUP_AND_STALE_TAB_CUTOVER_DRAFT.md
- docs/security/STALE_TAB_CUTOVER_RUNBOOK_DRAFT.md
- docs/security/LEGACY_TAB_ISOLATION_CUTOVER_DRAFT.md
- docs/security/LEGACY_EXHIBITION_WRITER_INVENTORY.md
- docs/security/VERSIONED_SUBSCRIBER_SCHEMA_DRAFT.sql

## 6. 推奨する次の作業順
A. 現在のコードでID対応、認証主体、undo所有権の前提を先に点検する。移行に必要な根本修正を決める。
B. Discoverを画面単位で完成させる。初回認証GET、既存登録を保持したフィルター、保存、取り消し、明示復元、結果不明の自動確認、dispose/復帰を一括で実装・検証する。
C. 同じ確立した経路をホームに接続する。4画面すべての旧handler・通知呼び出し・migrationへの影響をレビューする。
D. 旧形式データ移行と画面横断E2E。ブラウザ2context、同context2タブ、旧キャッシュタブ、削除/復元/順不同応答/期限切れ/復帰を検証する。
E. 導入手順と残存リスク、証拠一覧を仕上げる。ユーザーの承認はマージ・本番変更の直前に必要。

これらの順序は提案であり新たな承認条件ではない。合理的な改善は自律的に進める。
細かな変更ごとにユーザーへ「続けるか」を聞かない。作業を画面・機能単位にまとめる。
既存テストの成功だけで未接続経路を完了扱いしない。量より実入口と失敗ケースの整合を重視する。

## 7. 検証方法と証拠の読み方
最初に最新remote HEADとPR Checksを確認する。文書追加コミットのCIと、コード基準コミットのCIを区別する。
ローカルの基本コマンド（repo root）
```bash
node --test tests/test_draft*.cjs tests/draft_migration_review_explain.test.cjs
python -m unittest discover -s tests
python scripts/audit_legacy_exhibition_writers.py
git diff --check
```
Pythonにはflask==3.1.0とpsycopg[binary]==3.2.6が必要。使い捨てvenvで導入してよい。
Node単体はbuilt-in test runner。実ブラウザは@playwright/test==1.58.2とChromium。
ブラウザサーバー・対象spec・DB起動・TLS生成・環境変数は .github/workflows/private-subscriber-tests.yml を正本とする。
test_disposable_postgres_cas.pyは明示的な使い捨てDB名とlocalhostを要求し、schemaを作成する。各実行に空の使い捨てDBを用意する。
本番URLをテストに渡してはならない。

| CIジョブ | 証明する範囲 |
| --- | --- |
| synthetic-unit-tests | Pythonのモデル、HTTP認証、移行検証、監査 |
| browser-sync-tests | JSモデル・制御の合成テスト |
| draft-real-browser-e2e | 隔離HTML、抽出detailマークアップ、worker offline等 |
| draft-legacy-browser-e2e | 旧経路の互換性とDiscover等の実テンプレート由来fixture |
| disposable-postgres-cas | 実DB並行CAS、所有権/失効、実HTTPSブラウザ、別DB復元 |

disposable-postgres-casは以下も含む。
- tests/fixtures/serve_disposable_sync.pyを使い、loopback HTTPS 443でFlaskを起動。
- tests/disposable_sync_browser.spec.cjsで複数cookie sessionと実テンプレートを検証。
- 成功したconsume/POSTの応答だけをroute.fetch後にabortする失敗注入。
- pg_dumpから別の空DBへpg_restoreし、全source tableの全行を比較。
- read_only factoryによるPOST停止と既存状態の保持。
これは使い捨て環境の復旧証拠。独立保管・長期運用・本番切替の証明は残る。

詳細の古い抽出マークアップテストはJinjaの新分岐を正しく選ぶ必要がある。
最近の失敗は実装とfixtureが食い違ったものもある。実テストを弱めて通さず、実renderのテストと役割を確認する。
このChatGPT環境ではローカルChromiumがsocket制約で起動できない時期があり、実ブラウザはCIで実行した。Claude Code環境でも同じ制限があると仮定しない。

## 8. 引き継いだ修正の索引
| Commit | 内容 |
| --- | --- |
| aada244 | 最初の引き継ぎ基準 |
| 838bb58 | 曖昧保存のGET確認、復元issue/consumeへの修正 |
| f5e1e5a | 旧worker下のprivate read対策 |
| ef5cb0a | HTTPSブラウザ/Flask/DB統合、別DB復元、dispose中断 |
| afde858 | 共通reader、bootstrap readback、JSON構造比較 |
| bb314c1 | 追加移行の保存確認 |
| 70438d9 | 旧形式移行の実ブラウザ/DB試験 |
| effaa3b | 実detailテンプレート隔離接続、fixture分岐修正 |
| f8b1730 | detail明示復元 |
| 1713e69 | nearby実テンプレート接続 |
| 64ee5df | reconnect/persisted lifecycle |
| 95f885e | Discover既存登録をundoで消さない |
| 3953c77 | Discover認証APIのflow経路 |

## 9. 引き継ぎ完了時の状態と作業上の注意
すべてDraft PR内。最終の実装CIは上記3953c77で5件成功。引き継ぎ文書の追加ではアプリコードを変えない。
提供者は直近チェックアウトをこのfeature branchと同期済み。Claude Codeは自身の環境で必ず確認する。
通常git pushはChatGPT環境で認証不可だったため、GitHub connectorのtree/commit/ref APIを使用した。Claude Codeでは通常のgit/ghでよい。ref更新は最新headを確認し、競合したら再読込する。
PRは巨大で、aada244時点で784コミット/210ファイルだった。無関係な履歴書換えや一括整形を避ける。app.pyは改行差分が大きい箇所があり、git diff -wも併用する。
未使用/古いdraft helperが多数ある。削除・統合前にcallerを検索し、実際に使う経路と互換性を保つ。
次の進捗報告は「何画面・何経路が実際に完成したか」「何が未検証か」を中心にし、根拠のない完成率を更新しない。
