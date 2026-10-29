import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

class StealthBrowser:
    def __init__(self, headless=True):
        self.headless = headless
        self.browser = None
        self.context = None

    async def start(self, p):
        """Launches the browser with evasive arguments."""
        self.browser = await p.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        
        # Set a realistic user agent
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York"
        )
        
        # Apply stealth at the context level (v2.x API)
        await Stealth().apply_stealth_async(self.context)
        return self.context

    async def fetch_dom(self, url: str) -> str:
        """Navigates to a URL and returns the fully rendered DOM."""
        # Pages spawned from a stealthed context inherit the evasions automatically
        page = await self.context.new_page()
        
        try:
            # Wait until network activity settles to capture dynamic React/Angular loads
            await page.goto(url, wait_until="networkidle", timeout=20000)
            
            # Additional buffer for delayed travel API responses rendering in the UI
            await page.wait_for_timeout(3000) 
            
            html_content = await page.content()
            return html_content
            
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return ""
        finally:
            await page.close()

    async def close(self):
        if self.browser:
            await self.browser.close()

# Quick test execution
async def test_stealth():
    async with async_playwright() as p:
        engine = StealthBrowser(headless=False) # Set False to watch it work
        await engine.start(p)
        print("Navigating to test site...")
        
        dom = await engine.fetch_dom("https://bot.sannysoft.com/")
        
        print("\n--- HTML PAYLOAD (First 2000 characters) ---")
        print(dom[:2000])
        print("--------------------------------------------\n")
        
        if "WebDriver (New)" in dom:
            print("Successfully rendered page.")
            
        print("Holding browser open for 15 seconds for visual inspection...")
        await asyncio.sleep(15)
            
        await engine.close()

if __name__ == "__main__":
    asyncio.run(test_stealth())

if __name__ == "__main__":
    asyncio.run(test_stealth())