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

        # 1. 验证顶栏 44px
        header = await page.wait_for_selector("#canvasHeaderBar")
        header_box = await header.bounding_box()
        print(f"Canvas Header height: {header_box['height']}px (Expected ~44px)")
        assert abs(header_box['height'] - 44) <= 2.0, f"Header height mismatch: {header_box['height']}"

        # 2. 验证 AI 视图（夜间模式）
        suggest_box = await page.wait_for_selector("#appSuggestBox")
        input_dock = await page.wait_for_selector(".gpt-input-box")
        assert suggest_box is not None and input_dock is not None

        dark_ai_shot = os.path.join(ARTIFACT_DIR, "verify_mid_ai_workspace_dark.png")
        await main_el.screenshot(path=dark_ai_shot)
        print(f"Saved: {dark_ai_shot}")

        # 3. 验证本地回归视图（夜间模式）
        btn_local = await page.wait_for_selector("#btnModeLocal")
        await btn_local.click()
        await asyncio.sleep(0.6)

        # 验证分类跑道胶囊组
        tabs_capsule = await page.wait_for_selector(".local-filter-group-capsule")
        assert tabs_capsule is not None, "local-filter-group-capsule not found!"

        # 验证紧凑流线卡片
        compact_cards = await page.query_selector_all(".case-card-compact")
        print(f"Found {len(compact_cards)} compact case cards.")
        assert len(compact_cards) > 0, "No compact case cards found!"

        # 检查第一个卡片的高度 (预期 50px~60px)
        first_card_box = await compact_cards[0].bounding_box()
        print(f"Compact Case Card height (collapsed): {first_card_box['height']}px")
        assert first_card_box['height'] <= 65.0, f"Card too tall: {first_card_box['height']}"

        # 测试点击展开抽屉
        await compact_cards[0].click()
        await asyncio.sleep(0.3)
        expanded_card_box = await compact_cards[0].bounding_box()
        print(f"Compact Case Card height (expanded): {expanded_card_box['height']}px")
        assert expanded_card_box['height'] > first_card_box['height'], "Card drawer did not expand!"

        dark_local_shot = os.path.join(ARTIFACT_DIR, "verify_mid_local_workspace_dark.png")
        await main_el.screenshot(path=dark_local_shot)
        print(f"Saved: {dark_local_shot}")

        # 4. 验证白天模式 (Light Mode)
        print("Switching to light mode...")
        await page.evaluate("document.body.setAttribute('data-theme', 'light'); document.body.classList.add('theme-light');")
        await asyncio.sleep(0.4)

        light_local_shot = os.path.join(ARTIFACT_DIR, "verify_mid_local_workspace_light.png")
        await main_el.screenshot(path=light_local_shot)
        print(f"Saved: {light_local_shot}")

        # 切回 AI 视图并截取白天模式全貌
        btn_ai = await page.wait_for_selector("#btnModeAi")
        await btn_ai.click()
        await asyncio.sleep(0.5)

        light_ai_shot = os.path.join(ARTIFACT_DIR, "verify_mid_ai_workspace_light.png")
        await main_el.screenshot(path=light_ai_shot)
        print(f"Saved: {light_ai_shot}")

        # 全页面整体协同截图 (验证左侧栏与中间主工作台的一致性)
        full_light_shot = os.path.join(ARTIFACT_DIR, "verify_fullpage_linear_minimal_light.png")
        await page.screenshot(path=full_light_shot)
        print(f"Saved: {full_light_shot}")

        await page.evaluate("document.body.removeAttribute('data-theme'); document.body.classList.remove('theme-light');")
        await asyncio.sleep(0.3)
        full_dark_shot = os.path.join(ARTIFACT_DIR, "verify_fullpage_linear_minimal_dark.png")
        await page.screenshot(path=full_dark_shot)
        print(f"Saved: {full_dark_shot}")

        await browser.close()
        print("\n>>> ALL CHECKS PASSED: MID WORKSPACE UPGRADE VERIFIED! <<<")

if __name__ == "__main__":
    asyncio.run(main())
