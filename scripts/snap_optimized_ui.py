import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        # 截取主页面
        await page.screenshot(path="C:/Users/Administrator/.gemini/antigravity/brain/f3ec9076-9983-43bc-abf5-72fe8de4e2b6/verify_optimized_full.png")
        print("Full page screenshot saved.")
        
        # 截取顶部意图与任务清单区域
        stream_container = await page.query_selector("#streamConversationContainer")
        if stream_container:
            await stream_container.screenshot(path="C:/Users/Administrator/.gemini/antigravity/brain/f3ec9076-9983-43bc-abf5-72fe8de4e2b6/verify_optimized_stream.png")
            print("Stream container screenshot saved.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
