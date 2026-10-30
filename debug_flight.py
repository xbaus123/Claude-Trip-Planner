import asyncio
import sys
sys.path.append('tools')

from bs4 import BeautifulSoup
from browser_engine import StealthBrowser
from playwright.async_api import async_playwright

async def f():
    url = "https://www.kayak.com/flights/CRW-MCO/2026-11-10/2026-11-15?sort=price_a"
    engine = StealthBrowser(headless=True)
    async with async_playwright() as p:
        await engine.start(p)
        page = await engine.context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector("div.nrc6-wrapper", timeout=25000)
            await page.wait_for_timeout(3000)
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            print(str(soup.select_one("div.nrc6-wrapper")))
        except Exception as e:
            print(f"Failed: {e}")
        finally:
            await engine.close()

if __name__ == "__main__":
    asyncio.run(f())