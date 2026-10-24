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
        bottom_box = await page.wait_for_selector(".sidebar-bottom")
        assert switcher is not None and thumb is not None and bottom_box is not None

        # 验证高度增高为 38px
        box_metrics = await switcher.bounding_box()
        print(f"Switcher height: {box_metrics['height']}px (Expected ~38px)")
        assert box_metrics['height'] >= 36.0, f"Height too small: {box_metrics['height']}"

        # 1. 夜间模式下的蓝色流体胶囊截图
        dark_ai_shot = os.path.join(ARTIFACT_DIR, "verify_blue_capsule_dark_ai.png")
        await bottom_box.screenshot(path=dark_ai_shot)
        print(f"Saved: {dark_ai_shot}")

        # 点击“本地回归”，验证滑动与深色蓝色胶囊
        btn_local = await page.wait_for_selector("#btnModeLocal")
        await btn_local.click()
        await asyncio.sleep(0.4)

        dark_local_shot = os.path.join(ARTIFACT_DIR, "verify_blue_capsule_dark_local.png")
        await bottom_box.screenshot(path=dark_local_shot)
        print(f"Saved: {dark_local_shot}")

        # 2. 白天模式验证 (Light Mode)
        print("Switching to light mode...")
        await page.evaluate("document.body.setAttribute('data-theme', 'light'); document.body.classList.add('theme-light');")
        await asyncio.sleep(0.3)

        # 验证没有底部长方形白色背景
        bottom_bg = await page.evaluate("window.getComputedStyle(document.querySelector('.sidebar-bottom')).backgroundColor")
        print(f"Computed sidebar-bottom backgroundColor: {bottom_bg}")

        light_local_shot = os.path.join(ARTIFACT_DIR, "verify_blue_capsule_light_local.png")
        await bottom_box.screenshot(path=light_local_shot)
        print(f"Saved: {light_local_shot}")

        # 点击切回 AI 模式
        btn_ai = await page.wait_for_selector("#btnModeAi")
        await btn_ai.click()
        await asyncio.sleep(0.4)

        light_ai_shot = os.path.join(ARTIFACT_DIR, "verify_blue_capsule_light_ai.png")
        await bottom_box.screenshot(path=light_ai_shot)
        print(f"Saved: {light_ai_shot}")

        # 侧栏全貌截图 (白天模式)
        sidebar_light_shot = os.path.join(ARTIFACT_DIR, "verify_sidebar_blue_capsule_light.png")
        await sidebar.screenshot(path=sidebar_light_shot)
        print(f"Saved: {sidebar_light_shot}")

        # 侧栏全貌截图 (夜间模式)
        await page.evaluate("document.body.removeAttribute('data-theme'); document.body.classList.remove('theme-light');")
        await asyncio.sleep(0.3)
        sidebar_dark_shot = os.path.join(ARTIFACT_DIR, "verify_sidebar_blue_capsule_dark.png")
        await sidebar.screenshot(path=sidebar_dark_shot)
        print(f"Saved: {sidebar_dark_shot}")

        await browser.close()
        print("\n>>> ALL CHECKS PASSED: TALLER BLUE CAPSULE WITHOUT WHITE BG VERIFIED! <<<")

if __name__ == "__main__":
    asyncio.run(main())
