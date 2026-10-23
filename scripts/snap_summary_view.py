import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        # 寻找 test-result-summary-card 或最后一个元素并 scrollIntoView
        summary = await page.query_selector(".test-result-summary-card")
        if summary:
            await summary.scroll_into_view_if_needed()
            await page.wait_for_timeout(1000)
            await summary.screenshot(path="C:/Users/Administrator/.gemini/antigravity/brain/f3ec9076-9983-43bc-abf5-72fe8de4e2b6/verify_summary_card_view.png")
            print("Summary card screenshot saved.")
        else:
            print("Summary card not found.")
            
        # 截取整个页面的完整区域
        await page.screenshot(path="C:/Users/Administrator/.gemini/antigravity/brain/f3ec9076-9983-43bc-abf5-72fe8de4e2b6/verify_full_scrolled.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
