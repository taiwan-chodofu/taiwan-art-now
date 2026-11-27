from playwright.sync_api import sync_playwright
from pathlib import Path

Path("editorial-test-output").mkdir(exist_ok=True)
with sync_playwright() as p:
    for name, engine, options in [
        ("iphone", p.webkit, p.devices["iPhone 13"]),
        ("desktop", p.chromium, {"viewport": {"width": 1440, "height": 900}}),
    ]:
        browser = engine.launch()
        context = browser.new_context(**options)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("https://www.googletagmanager.com/**", lambda route: route.abort())
        response = page.goto("http://127.0.0.1:5050/essays/001?_exclude_ga=1")
        assert response.status == 200
        assert page.locator("#essay-body p").count() == 31
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=f"editorial-test-output/{name}-cover.png")
        page.locator("#share").scroll_into_view_if_needed()
        page.evaluate("Object.defineProperty(navigator, 'clipboard', {configurable:true,value:{writeText:async()=>{throw Error('blocked')}}})")
        page.locator("#copy-link").click()
        assert "請長按" in page.locator("#share-status").inner_text()
        page.locator("details summary").first.click()
        assert page.locator("details").first.get_attribute("open") is not None
        assert page.locator("details a").count() == 18
        page.locator(".explore").scroll_into_view_if_needed()
        page.screenshot(path=f"editorial-test-output/{name}-navigation.png")
        assert not errors, errors
        browser.close()
