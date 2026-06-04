"""Facebook認証セットアップ: 手動ログイン後にCookieを保存する"""
from playwright.sync_api import sync_playwright

print("Facebookログイン用ブラウザを起動します...")
print("1. Facebookにログインしてください")
print("2. 2FA（二段階認証）も完了してください")
print("3. ホーム画面が表示されたら、ここに戻ってEnterを押してください")
print()

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
        slow_mo=100,
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()
    page.goto("https://www.facebook.com/login")

    input("\n>>> FBにログイン完了したらEnterを押してください... ")

    context.storage_state(path="fb_state.json")
    print("\n✅ 認証情報を fb_state.json に保存しました！")
    print("これで home_scraper.py が動くようになります。")
    browser.close()
