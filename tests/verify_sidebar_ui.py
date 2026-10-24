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

        # 1. 验证默认侧栏宽度 (240px) 下，switcher 尺寸固定为 196px x 38px
        box_metrics = await switcher.bounding_box()
        print(f"Default switcher metrics: width={box_metrics['width']}px, height={box_metrics['height']}px")
        assert abs(box_metrics['width'] - 196) <= 2.0, f"Width not fixed to 196px: {box_metrics['width']}"
        assert abs(box_metrics['height'] - 38) <= 2.0, f"Height not fixed to 38px: {box_metrics['height']}"

        # 2. 模拟用户将侧栏拖拽拉宽至 380px
        print("Expanding sidebar width to 380px...")
        await page.evaluate("document.getElementById('gptSidebar').style.width = '380px';")
        await asyncio.sleep(0.3)

        # 再次获取 switcher 尺寸
        expanded_metrics = await switcher.bounding_box()
        print(f"Expanded sidebar switcher metrics: width={expanded_metrics['width']}px, height={expanded_metrics['height']}px")
        assert abs(expanded_metrics['width'] - 196) <= 2.0, f"Switcher width changed when sidebar expanded: {expanded_metrics['width']}"

        # 3. 验证在拉宽状态下，点击切换“本地回归”滑块顺滑滑动，保持居中
        btn_local = await page.wait_for_selector("#btnModeLocal")
        await btn_local.click()
        await asyncio.sleep(0.4)

        # 截取深色模式下拉宽侧栏的全局效果
        expanded_dark_shot = os.path.join(ARTIFACT_DIR, "verify_fixed_capsule_expanded_dark.png")
        await sidebar.screenshot(path=expanded_dark_shot)
        print(f"Saved: {expanded_dark_shot}")

        # 4. 切换到白天模式并切回 AI 模式
        print("Switching to light mode...")
        await page.evaluate("document.body.setAttribute('data-theme', 'light'); document.body.classList.add('theme-light');")
        await asyncio.sleep(0.3)

        btn_ai = await page.wait_for_selector("#btnModeAi")
        await btn_ai.click()
        await asyncio.sleep(0.4)

        # 截取白天模式下拉宽侧栏的全局效果
        expanded_light_shot = os.path.join(ARTIFACT_DIR, "verify_fixed_capsule_expanded_light.png")
        await sidebar.screenshot(path=expanded_light_shot)
        print(f"Saved: {expanded_light_shot}")

        # 5. 还原侧栏为默认 240px，截取标准形态
        await page.evaluate("document.getElementById('gptSidebar').style.width = '240px';")
        await asyncio.sleep(0.3)

        standard_light_shot = os.path.join(ARTIFACT_DIR, "verify_fixed_capsule_standard_light.png")
        await sidebar.screenshot(path=standard_light_shot)
        print(f"Saved: {standard_light_shot}")

        await browser.close()
        print("\n>>> ALL CHECKS PASSED: FIXED 196x38 CAPSULE WON'T STRETCH ON EXPAND! <<<")

if __name__ == "__main__":
    asyncio.run(main())
