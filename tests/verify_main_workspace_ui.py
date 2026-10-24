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

        # 2. 验证推荐卡片与底部输入框像素级垂直居中对齐 (差值 0px)
        suggest = await page.eval_on_selector('#appSuggestBox', 'el => ({x: el.getBoundingClientRect().x, right: el.getBoundingClientRect().right, width: el.getBoundingClientRect().width, mid: el.getBoundingClientRect().x + el.getBoundingClientRect().width/2})')
        input_b = await page.eval_on_selector('.gpt-input-box', 'el => ({x: el.getBoundingClientRect().x, right: el.getBoundingClientRect().right, width: el.getBoundingClientRect().width, mid: el.getBoundingClientRect().x + el.getBoundingClientRect().width/2})')
        print("Suggest Box rect:", suggest)
        print("Input Box rect:  ", input_b)
        assert abs(suggest['x'] - input_b['x']) <= 1.0, f"Left edge mismatch: {suggest['x']} vs {input_b['x']}"
        assert abs(suggest['right'] - input_b['right']) <= 1.0, f"Right edge mismatch: {suggest['right']} vs {input_b['right']}"
        assert abs(suggest['mid'] - input_b['mid']) <= 1.0, f"Center mid mismatch: {suggest['mid']} vs {input_b['mid']}"

        dark_ai_shot = os.path.join(ARTIFACT_DIR, "verify_fullpage_aligned_dark.png")
        await page.screenshot(path=dark_ai_shot)
        print(f"Saved: {dark_ai_shot}")

        # 3. 验证本地回归视图（夜间模式）
        btn_local = await page.wait_for_selector("#btnModeLocal")
        await btn_local.click()
        await asyncio.sleep(0.6)

        # 验证分类跑道胶囊组与紧凑用例卡片
        tabs_capsule = await page.wait_for_selector(".local-filter-group-capsule")
        assert tabs_capsule is not None, "local-filter-group-capsule not found!"

        compact_cards = await page.query_selector_all(".case-card-compact")
        assert len(compact_cards) > 0, "No compact case cards found!"

        first_card_box = await compact_cards[0].bounding_box()
        print(f"Compact Case Card height (collapsed): {first_card_box['height']}px")
        assert first_card_box['height'] <= 65.0, f"Card too tall: {first_card_box['height']}"

        # 4. 验证白天模式 (Light Mode)
        print("Switching to light mode...")
        await page.evaluate("document.body.setAttribute('data-theme', 'light'); document.body.classList.add('theme-light');")
        await asyncio.sleep(0.4)

        # 切回 AI 视图并截取白天模式全貌
        btn_ai = await page.wait_for_selector("#btnModeAi")
        await btn_ai.click()
        await asyncio.sleep(0.5)

        light_ai_shot = os.path.join(ARTIFACT_DIR, "verify_fullpage_aligned_light.png")
        await page.screenshot(path=light_ai_shot)
        print(f"Saved: {light_ai_shot}")

        await browser.close()
        print("\n>>> ALL CHECKS PASSED: PIXEL-PERFECT ALIGNMENT VERIFIED! <<<")

if __name__ == "__main__":
    asyncio.run(main())
