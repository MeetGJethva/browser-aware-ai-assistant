from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        self.current_url = None
        self.page_text = ""

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.page = await self.browser.new_page()

    # async def load_url(self, url: str):
    #     if not self.page:
    #         await self.start()

    #     await self.page.goto(url)
    #     self.current_url = url
    #     await self.extract_content()

    async def extract_content(self):
        html = await self.page.content()
        soup = BeautifulSoup(html, "html.parser")

        for script in soup(["script", "style"]):
            script.decompose()

        self.page_text = soup.get_text(separator="\n")

    async def close(self):
        if self.browser:
            await self.browser.close()
            await self.playwright.stop()

    async def load_url(self, url: str):
        if not self.page:
            await self.start()

        await self.page.goto(url)
        self.current_url = url

        await self.page.wait_for_load_state("networkidle")
        await self.extract_content()

browser_manager = BrowserManager()