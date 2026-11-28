from playwright.sync_api import sync_playwright
from pathlib import Path

Path("editorial-test-output").mkdir(exist_ok=True)
with sync_playwright() as p:
    for name, engine, options in [
        ("iphone", p.webkit, p.devices["iPhone 13"]),
        ("small320", p.webkit, {"viewport":{"width":320,"height":640},"is_mobile":True,"has_touch":True}),
        ("mobile375", p.webkit, {"viewport":{"width":375,"height":812},"is_mobile":True,"has_touch":True}),
        ("mobile430", p.webkit, {"viewport":{"width":430,"height":932},"is_mobile":True,"has_touch":True}),
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
        footer_brand = page.locator(".footer-brand").bounding_box()
        footer_url = page.locator(".footer-url").bounding_box()
        assert footer_url["y"] >= footer_brand["y"] + footer_brand["height"]
        assert page.locator("#copy-link").bounding_box()["height"] >= 44
        assert page.locator("#essay-body").evaluate("(el) => parseFloat(getComputedStyle(el).fontSize)") >= 18
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
        page.locator('nav[aria-label="文章版本"] a[href="/essays/001/second"]').click()
        assert page.url.endswith("/essays/001/second")
        assert page.locator("#essay-body h2").count() == 8
        assert page.locator("#essay-body p").count() > 200
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=f"editorial-test-output/{name}-second-cover.png")
        toc = page.locator('nav[aria-label="目錄"] a')
        assert toc.count() == 8
        assert toc.first.bounding_box()["height"] >= 44
        toc.first.scroll_into_view_if_needed()
        page.screenshot(path=f"editorial-test-output/{name}-second-toc.png")
        toc.nth(7).click()
        assert page.url.endswith("#chapter-8")
        assert page.locator("#chapter-8").is_in_viewport() if hasattr(page.locator("#chapter-8"), "is_in_viewport") else page.locator("#chapter-8").evaluate("(el) => el.getBoundingClientRect().top >= 0 && el.getBoundingClientRect().top < innerHeight")
        page.screenshot(path=f"editorial-test-output/{name}-second-chapter.png")
        assert "投下一票的，是一個人。" in page.locator("#essay-body").inner_text()
        page.locator("#share").scroll_into_view_if_needed()
        assert page.locator("#share-url").input_value().endswith("/essays/001/second")
        page.locator("details summary").first.click()
        assert page.locator("details a").count() == 28
        page.locator('nav[aria-label="文章版本"] a[href="/essays/001"]').click()
        assert page.url.endswith("/essays/001")
        assert page.locator("#essay-body p").count() == 31
        assert not errors, errors
        browser.close()
