# Taiwan Art Now — 家PCセットアップ手順書

このファイルの手順を家PCの前で順番にやれば、家PC単独で運用できます。

---

## 前提（昨日完了済み）

- Python 3.14 ✅
- Git ✅
- Playwright + chromium ✅
- プロジェクト: `C:\Users\Go\taiwan-art-now` ✅

---

## Step 1: GitHubへのpush認証を設定する（5分）

コマンドプロンプトを開いて:

```
cd C:\Users\Go\taiwan-art-now
git remote set-url origin https://taiwan-chodofu:YOUR_TOKEN_HERE@github.com/taiwan-chodofu/taiwan-art-now.git
```

`YOUR_TOKEN_HERE` を自分のGitHub Classic tokenに置き換えてください。

**トークン発行方法**:
1. https://github.com/settings/tokens/new を開く
2. Note: `push` / Expiration: 90 days / Scopes: `repo` にチェック
3. Generate token → `ghp_` で始まる文字列をコピー

これで以後 `git push origin main` だけでpushできます。

---

## Step 2: Facebook認証（storageState保存）（10分）

### 2-1. ログインスクリプトを実行

```
cd C:\Users\Go\taiwan-art-now
python fb_login.py
```

ブラウザが開きます:
1. Facebookにログインしてください
2. 2FA（二段階認証）も完了してください
3. ホーム画面が表示されたら、コマンドプロンプトに戻ってEnterを押す

**2FAの画面が壊れた場合**: ブラウザのURLバーに `https://www.facebook.com` と直接入力してEnter。既にログインが通っている場合があります。ホーム画面が出たらEnter。

成功すると `fb_state.json` が作成されます。

---

## Step 3: スクレイパーを実行

```
cd C:\Users\Go\taiwan-art-now
git pull
python home_scraper.py
```

Facebook施設の展覧会データが `fb_exhibitions.json` に保存されます。

---

## Step 4: 結果をpushする

```
cd C:\Users\Go\taiwan-art-now
git add fb_exhibitions.json
git commit -m "update fb exhibitions data"
git push origin main
```

Renderが自動デプロイしてサイトに反映されます。

---

## 日常の運用（週1回程度）

```
cd C:\Users\Go\taiwan-art-now
git pull
python home_scraper.py
git add fb_exhibitions.json
git commit -m "update fb exhibitions"
git push origin main
```

これだけ。5分で完了。

---

## トラブルシューティング

| 問題 | 解決策 |
|------|--------|
| fb_state.json の期限切れ（ログインウォールが出る） | `python fb_login.py` を再実行 |
| git push が 403 | GitHub tokenが失効。新しいClassic tokenを発行してStep 1をやり直す |
| playwright関連エラー | `python -m playwright install chromium` を再実行 |

---

**リポジトリ**: https://github.com/taiwan-chodofu/taiwan-art-now
**サイト**: https://taiwan-art-now.onrender.com/
