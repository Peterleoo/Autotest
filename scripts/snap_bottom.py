import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        # 滚到底部
        await page.evaluate("const el = document.getElementById('streamConversationContainer'); if(el) el.scrollTop = el.scrollHeight;")
        await page.wait_for_timeout(1000)
        
        await page.screenshot(path="C:/Users/Administrator/.gemini/antigravity/brain/f3ec9076-9983-43bc-abf5-72fe8de4e2b6/verify_optimized_bottom.png")
        print("Bottom screenshot saved.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
