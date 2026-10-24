# -*- coding: utf-8 -*-
import os
import asyncio
from playwright.async_api import async_playwright

ARTIFACT_DIR = r"C:\Users\Administrator\.gemini\antigravity\brain\aba39f35-e849-49b7-8803-1f8c65a65dd7"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel="msedge")
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        print("Navigating to http://127.0.0.1:8000/ ...")
        await page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        await asyncio.sleep(1.5)

        sidebar = await page.wait_for_selector("#gptSidebar", timeout=5000)
        assert sidebar is not None, "Sidebar not found!"

        switcher = await page.wait_for_selector("#sidebarModeSwitcher")
        thumb = await page.wait_for_selector("#modeSliderThumb")
        assert switcher is not None and thumb is not None, "Liquid slider switcher/thumb not found!"

        # 1. 验证没有残留的数字药丸，没有多余图标
        count_pills = await page.query_selector_all(".mode-count-pill")
        assert len(count_pills) == 0, "All mode-count-pills should be completely removed!"
        icons = await switcher.query_selector_all("i")
        assert len(icons) == 0, "No extra icons should be inside segmented control!"

        # 2. 验证深色模式下流体滑块在 AI 模式的状态
        bottom_box = await page.wait_for_selector(".sidebar-bottom")
        dark_ai_shot = os.path.join(ARTIFACT_DIR, "verify_apple_liquid_capsule_dark_ai.png")
        await bottom_box.screenshot(path=dark_ai_shot)
        print(f"Saved: {dark_ai_shot}")

        # 3. 点击“本地回归”，验证阻尼滑动和 is-local 状态
        btn_local = await page.wait_for_selector("#btnModeLocal")
        await btn_local.click()
        await asyncio.sleep(0.4)  # 等待 260ms 阻尼动画完成

        is_local_class = await switcher.get_attribute("class")
        assert "is-local" in is_local_class, "Switcher should have 'is-local' class!"

        dark_local_shot = os.path.join(ARTIFACT_DIR, "verify_apple_liquid_capsule_dark_local.png")
        await bottom_box.screenshot(path=dark_local_shot)
        print(f"Saved: {dark_local_shot}")

        # 4. 验证白天模式 (Light Mode) 下的苹果微浮动纯白卡片与浅灰底槽
        print("Switching to light mode...")
        await page.evaluate("document.body.setAttribute('data-theme', 'light'); document.body.classList.add('theme-light');")
        await asyncio.sleep(0.3)

        light_local_shot = os.path.join(ARTIFACT_DIR, "verify_apple_liquid_capsule_light_local.png")
        await bottom_box.screenshot(path=light_local_shot)
        print(f"Saved: {light_local_shot}")

        # 点击切回 AI 模式，验证白天模式下滑块丝滑回弹
        btn_ai = await page.wait_for_selector("#btnModeAi")
        await btn_ai.click()
        await asyncio.sleep(0.4)

        is_local_class_after = await switcher.get_attribute("class")
        assert "is-local" not in is_local_class_after, "Switcher should NOT have 'is-local' class!"

        light_ai_shot = os.path.join(ARTIFACT_DIR, "verify_apple_liquid_capsule_light_ai.png")
        await bottom_box.screenshot(path=light_ai_shot)
        print(f"Saved: {light_ai_shot}")

        # 5. 白天模式下侧边栏整体截图
        sidebar_light_shot = os.path.join(ARTIFACT_DIR, "verify_sidebar_apple_capsule_light.png")
        await sidebar.screenshot(path=sidebar_light_shot)
        print(f"Saved: {sidebar_light_shot}")

        await browser.close()
        print("\n>>> ALL CHECKS PASSED: APPLE LIQUID SLIDING CAPSULE VERIFIED! <<<")

if __name__ == "__main__":
    asyncio.run(main())
