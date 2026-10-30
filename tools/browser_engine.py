import asyncio
import random
import re
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# Each profile is a complete, internally consistent desktop identity. Rotating the
# User-Agent alone is counter-productive: anti-bot systems cross-check it against
# navigator.platform, the sec-ch-ua-* client-hint headers, navigator.userAgentData,
# WebGL, and screen size, so every one of those is drawn from the same profile.
#
# The Chrome *version* is never randomized. It is read from the Chromium that
# Playwright actually launched, because claiming a different version than the
# engine is easy to detect from JS feature checks and the real userAgentData.
OS_PROFILES = [
    {
        "os": "Windows",
        "weight": 70,  # roughly matches real desktop Chrome market share
        "ua_os": "Windows NT 10.0; Win64; x64",  # frozen by Chrome's UA reduction, even on Windows 11
        "navigator_platform": "Win32",
        "platform_versions": ["10.0.0", "15.0.0", "19.0.0"],  # Win10, Win11 23H2, Win11 24H2
        "architecture": "x86",
        "screens": [  # (width, height, device_scale_factor)
            (1920, 1080, 1), (1920, 1080, 1.25), (1536, 864, 1.25), (1366, 768, 1), (2560, 1440, 1),
        ],
        "taskbar_px": 48,
        "gpus": [
            ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 620 (0x00003EA0) Direct3D11 vs_5_0 ps_5_0, D3D11)"),
            ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics (0x000046A8) Direct3D11 vs_5_0 ps_5_0, D3D11)"),
            ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 (0x00002504) Direct3D11 vs_5_0 ps_5_0, D3D11)"),
            ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon(TM) Graphics (0x00001638) Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ],
        "cores": [4, 8, 12, 16],
    },
    {
        "os": "macOS",
        "weight": 30,
        "ua_os": "Macintosh; Intel Mac OS X 10_15_7",  # frozen by Chrome, even on Apple Silicon
        "navigator_platform": "MacIntel",
        "platform_versions": ["14.7.1", "15.5.0", "15.6.1", "26.0.1"],
        "architecture": "arm",
        "screens": [(1440, 900, 2), (1512, 982, 2), (1728, 1117, 2), (1470, 956, 2)],
        "taskbar_px": 25,  # menu bar
        "gpus": [
            ("Google Inc. (Apple)", "ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)"),
            ("Google Inc. (Apple)", "ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version)"),
            ("Google Inc. (Apple)", "ANGLE (Apple, ANGLE Metal Renderer: Apple M3 Pro, Unspecified Version)"),
        ],
        "cores": [8, 10, 12],
    },
]

BROWSER_CHROME_PX = 85  # tab strip + address bar eaten out of the window height


def build_fingerprint(chrome_full_version, rng=random):
    """Picks a random OS profile and builds a consistent fingerprint for the given Chrome version."""
    profile = rng.choices(OS_PROFILES, weights=[p["weight"] for p in OS_PROFILES])[0]
    major = chrome_full_version.split(".")[0]
    width, height, scale = rng.choice(profile["screens"])
    gpu_vendor, gpu_renderer = rng.choice(profile["gpus"])
    user_agent = (
        f"Mozilla/5.0 ({profile['ua_os']}) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"
    )
    return {
        "os": profile["os"],
        "user_agent": user_agent,
        "navigator_platform": profile["navigator_platform"],
        "platform_version": rng.choice(profile["platform_versions"]),
        "architecture": profile["architecture"],
        "chrome_major": major,
        "chrome_full_version": chrome_full_version,
        "screen": {"width": width, "height": height},
        "viewport": {"width": width, "height": height - profile["taskbar_px"] - BROWSER_CHROME_PX},
        "device_scale_factor": scale,
        "webgl_vendor": gpu_vendor,
        "webgl_renderer": gpu_renderer,
        "hardware_concurrency": rng.choice(profile["cores"]),
    }


def _brands(user_agent):
    """Chrome's GREASEd brand list (same algorithm stealth uses for the sec-ch-ua header)."""
    header = Stealth._get_greased_chrome_sec_ua_ch(user_agent)
    brands = [{"brand": b, "version": v} for b, v in re.findall(r'"([^"]+)";v="([^"]+)"', header)]
    for b in brands:  # stealth's helper says "Chrome"; real Google Chrome reports "Google Chrome"
        if b["brand"] == "Chrome":
            b["brand"] = "Google Chrome"
    return brands


def _full_version_list(brands, full_version):
    """Same brands, same order: real brands get the full version, the GREASE brand gets x.0.0.0."""
    return [
        {"brand": b["brand"],
         "version": full_version if b["brand"] in ("Chromium", "Google Chrome") else f"{b['version']}.0.0.0"}
        for b in brands
    ]


class StealthBrowser:
    def __init__(self, headless=True, seed=None):
        self.headless = headless
        self.browser = None
        self.context = None
        self.fingerprint = None
        self._rng = random.Random(seed)  # pass a seed to reproduce a specific identity while debugging

    async def start(self, p):
        """Launches the browser with evasive arguments and a freshly randomized identity."""
        self.browser = await p.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        fp = self.fingerprint = build_fingerprint(self.browser.version, self._rng)
        # Generated once per session: the GREASE brand must stay identical across pages and hint lists
        fp["brands"] = _brands(fp["user_agent"])
        print(f"🕵️  Browser identity: Chrome {fp['chrome_major']} on {fp['os']} {fp['platform_version']}, "
              f"{fp['screen']['width']}x{fp['screen']['height']}, {fp['hardware_concurrency']} cores")

        self.context = await self.browser.new_context(
            user_agent=fp["user_agent"],
            viewport=fp["viewport"],
            screen=fp["screen"],
            device_scale_factor=fp["device_scale_factor"],
            # Kept fixed on purpose: these should match your real IP's location, not rotate
            locale="en-US",
            timezone_id="America/New_York"
        )

        # Apply stealth at the context level (v2.x API), told about this run's identity so its
        # evasions agree with it instead of using their built-in Win32 / Intel / 4-core defaults.
        await Stealth(
            navigator_user_agent_override=fp["user_agent"],
            navigator_platform_override=fp["navigator_platform"],
            webgl_vendor_override=fp["webgl_vendor"],
            webgl_renderer_override=fp["webgl_renderer"],
            navigator_hardware_concurrency=False,  # stealth hard-codes 4; we set our own below
            sec_ch_ua=False,  # Chrome now generates every sec-ch-ua-* header from the metadata in new_page()
        ).apply_stealth_async(self.context)
        await self.context.add_init_script(
            "Object.defineProperty(Object.getPrototypeOf(navigator), 'hardwareConcurrency', "
            f"{{get: () => {fp['hardware_concurrency']}}});"
        )
        return self.context

    async def new_page(self):
        """Opens a page whose UA, client hints and userAgentData all match this run's identity.

        Always use this instead of `self.context.new_page()`: Playwright's user_agent option only
        changes the UA string, leaving sec-ch-ua-platform and navigator.userAgentData reporting the
        real OS. The CDP override below makes Chrome itself report the spoofed profile everywhere.
        """
        page = await self.context.new_page()
        fp = self.fingerprint
        cdp = await self.context.new_cdp_session(page)
        await cdp.send("Emulation.setUserAgentOverride", {
            "userAgent": fp["user_agent"],
            "acceptLanguage": "en-US,en;q=0.9",
            "platform": fp["navigator_platform"],
            "userAgentMetadata": {
                "brands": fp["brands"],
                "fullVersionList": _full_version_list(fp["brands"], fp["chrome_full_version"]),
                "fullVersion": fp["chrome_full_version"],
                "platform": fp["os"],
                "platformVersion": fp["platform_version"],
                "architecture": fp["architecture"],
                "model": "",
                "mobile": False,
                "bitness": "64",
                "wow64": False,
            },
        })
        return page

    async def fetch_dom(self, url: str) -> str:
        """Navigates to a URL and returns the fully rendered DOM."""
        page = await self.new_page()

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
