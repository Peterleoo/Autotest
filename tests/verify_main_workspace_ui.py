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

        main_el = await page.wait_for_selector("#gptMain")
        assert main_el is not None, "gptMain not found!"

        # 1. 验证顶栏背景在白天与夜间均为透明，高度 44px
        header = await page.wait_for_selector("#canvasHeaderBar")
        header_box = await header.bounding_box()
        print(f"Canvas Header height: {header_box['height']}px (Expected ~44px)")
        assert abs(header_box['height'] - 44) <= 2.0

        bg_dark = await page.evaluate("window.getComputedStyle(document.getElementById('canvasHeaderBar')).backgroundColor")
        print(f"Dark mode canvas-header bg: {bg_dark}")
        assert "rgba(0, 0, 0, 0)" in bg_dark or "transparent" in bg_dark

        # 2. 验证右侧明细面板仅保留纯图标，无文本
        btn_right = await page.wait_for_selector("#btnToggleRight")
        btn_text = (await btn_right.inner_text()).strip()
        print(f"btnToggleRight text: '{btn_text}' (Expected empty)")
        assert btn_text == "", f"Button should only have an icon, but got text: '{btn_text}'"

        # 3. 验证新任务空状态下左侧标题绝对隐藏
        meta_visible = await page.evaluate("document.getElementById('activeTaskMeta').classList.contains('d-none')")
        print(f"activeTaskMeta hidden in new chat: {meta_visible}")
        assert meta_visible is True, "activeTaskMeta should be hidden in new chat!"

        header_dark_shot = os.path.join(ARTIFACT_DIR, "verify_header_minimal_dark.png")
        await header.screenshot(path=header_dark_shot)
        print(f"Saved: {header_dark_shot}")

        # 4. 验证本地回归模式下左侧标题同样绝对隐藏
        btn_local = await page.wait_for_selector("#btnModeLocal")
        await btn_local.click()
        await asyncio.sleep(0.5)

        meta_visible_local = await page.evaluate("document.getElementById('activeTaskMeta').classList.contains('d-none')")
        print(f"activeTaskMeta hidden in local mode: {meta_visible_local}")
        assert meta_visible_local is True, "activeTaskMeta should be hidden in local mode!"

        # 5. 白天模式验证
        print("Switching to light mode...")
        await page.evaluate("document.body.setAttribute('data-theme', 'light'); document.body.classList.add('theme-light');")
        await asyncio.sleep(0.3)

        bg_light = await page.evaluate("window.getComputedStyle(document.getElementById('canvasHeaderBar')).backgroundColor")
        print(f"Light mode canvas-header bg: {bg_light}")
        assert "rgba(0, 0, 0, 0)" in bg_light or "transparent" in bg_light

        header_light_shot = os.path.join(ARTIFACT_DIR, "verify_header_minimal_light.png")
        await header.screenshot(path=header_light_shot)
        print(f"Saved: {header_light_shot}")

        # 切回 AI 模式并截取全屏存证
        btn_ai = await page.wait_for_selector("#btnModeAi")
        await btn_ai.click()
        await asyncio.sleep(0.4)

        full_light = os.path.join(ARTIFACT_DIR, "verify_fullpage_header_clean_light.png")
        await page.screenshot(path=full_light)
        print(f"Saved: {full_light}")

        await page.evaluate("document.body.removeAttribute('data-theme'); document.body.classList.remove('theme-light');")
        await asyncio.sleep(0.3)
        full_dark = os.path.join(ARTIFACT_DIR, "verify_fullpage_header_clean_dark.png")
        await page.screenshot(path=full_dark)
        print(f"Saved: {full_dark}")

        await browser.close()
        print("\n>>> ALL CHECKS PASSED: CANVAS HEADER MINIMAL CLEANUP VERIFIED! <<<")

if __name__ == "__main__":
    asyncio.run(main())
