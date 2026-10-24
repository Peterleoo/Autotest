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

        # 1. 验证左侧边栏与新建按钮
        btn_new = await page.wait_for_selector(".btn-new-task", timeout=5000)
        assert btn_new is not None, "Hero CTA button .btn-new-task not found!"
        btn_text = await btn_new.inner_text()
        print("Hero CTA button text:", repr(btn_text))

        # 2. 验证搜索框
        search_inp = await page.wait_for_selector("#sessionSearchInput", timeout=3000)
        assert search_inp is not None, "Search input #sessionSearchInput not found!"
        placeholder = await search_inp.get_attribute("placeholder")
        print("Search input found with placeholder:", repr(placeholder))

        # 3. 验证时间分组标题
        headers = await page.query_selector_all(".session-group-header")
        print(f"Found {len(headers)} session group headers:")
        for h in headers:
            txt = await h.inner_text()
            print("  Group header:", repr(txt))
        assert len(headers) > 0, "No .session-group-header found!"

        # 4. 验证双行微卡片
        items = await page.query_selector_all(".session-item")
        print(f"Found {len(items)} session items.")
        assert len(items) > 0, "No .session-item found!"

        first_item = items[0]
        # 鼠标悬浮在首个 item 上
        await first_item.hover()
        await asyncio.sleep(0.5)

        # 验证悬浮操作按钮
        actions = await first_item.query_selector(".session-actions")
        assert actions is not None, "Actions menu not found in session item!"

        # 截图深色模式左侧栏
        sidebar = await page.query_selector("#gptSidebar")
        dark_shot_path = os.path.join(ARTIFACT_DIR, "verify_sidebar_ui_dark.png")
        if sidebar:
            await sidebar.screenshot(path=dark_shot_path)
            print(f"Dark mode sidebar screenshot saved: {dark_shot_path}")

        # 5. 验证即时搜索交互
        print("Testing inline search...")
        await search_inp.fill("房源")
        await asyncio.sleep(0.5)
        filtered_items = await page.query_selector_all(".session-item")
        print(f"Filtered items count for '房源': {len(filtered_items)}")

        # 截图搜索结果状态
        search_shot_path = os.path.join(ARTIFACT_DIR, "verify_sidebar_search_result.png")
        if sidebar:
            await sidebar.screenshot(path=search_shot_path)
            print(f"Search result screenshot saved: {search_shot_path}")

        # 清空搜索
        clear_btn = await page.wait_for_selector("#sessionSearchClear", state="visible", timeout=2000)
        await clear_btn.click()
        await asyncio.sleep(0.5)
        restored_items = await page.query_selector_all(".session-item")
        print(f"Restored items count after clear: {len(restored_items)}")
        assert len(restored_items) == len(items), "Clear search failed to restore full list!"

        # 6. 验证快捷键 Ctrl+F
        print("Testing Ctrl+F shortcut...")
        # 聚焦到页面主体其他区域
        await page.click("body")
        await page.keyboard.press("Control+F")
        await asyncio.sleep(0.3)
        is_focused = await page.evaluate("document.activeElement.id === 'sessionSearchInput'")
        print("Search input focused via Ctrl+F:", is_focused)
        assert is_focused, "Ctrl+F failed to focus sessionSearchInput"

        # 7. 验证浅色模式 (Light Theme)
        print("Switching to light mode...")
        await page.evaluate("document.body.setAttribute('data-theme', 'light'); document.body.classList.add('theme-light');")
        await asyncio.sleep(0.5)

        light_shot_path = os.path.join(ARTIFACT_DIR, "verify_sidebar_ui_light.png")
        if sidebar:
            await sidebar.screenshot(path=light_shot_path)
            print(f"Light mode sidebar screenshot saved: {light_shot_path}")

        # 截取浅色全屏
        full_light_path = os.path.join(ARTIFACT_DIR, "verify_fullpage_light.png")
        await page.screenshot(path=full_light_path)
        print(f"Fullpage light screenshot saved: {full_light_path}")

        await browser.close()
        print(">>> ALL SIDEBAR UI VERIFICATIONS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    asyncio.run(main())
