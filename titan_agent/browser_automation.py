from playwright.async_api import async_playwright, Page, Browser, Playwright
import asyncio
from pathlib import Path
from typing import Any

class BrowserAutomation:
    """Playwright-based browser automation for Titan Agent.
    Maintains a persistent browser session across tool calls.
    """
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.page: Page | None = None

    async def ensure_page(self) -> Page:
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
        return self.page

    async def tool_browser_goto(self, url: str) -> str:
        try:
            page = await self.ensure_page()
            await page.goto(url, wait_until="networkidle")
            return f"Successfully navigated to {url}"
        except Exception as e:
            return f"Error navigating to {url}: {e}"

    async def tool_browser_click(self, selector: str) -> str:
        try:
            page = await self.ensure_page()
            await page.click(selector)
            return f"Clicked on selector: {selector}"
        except Exception as e:
            return f"Error clicking selector {selector}: {e}"

    async def tool_browser_type(self, selector: str, text: str) -> str:
        try:
            page = await self.ensure_page()
            await page.fill(selector, text)
            return f"Filled {selector} with provided text."
        except Exception as e:
            return f"Error typing into {selector}: {e}"

    async def tool_browser_screenshot(self, filename: str = "screenshot.png") -> str:
        try:
            page = await self.ensure_page()
            path = self.workspace / filename
            await page.screenshot(path=path)
            return f"Screenshot successfully saved to {path}"
        except Exception as e:
            return f"Error taking screenshot: {e}"

    async def tool_browser_extract_text(self) -> str:
        try:
            page = await self.ensure_page()
            text = await page.evaluate("document.body.innerText")
            if len(text) > 4000:
                text = text[:4000] + "\n...(truncated)"
            return f"Page text content:\n{text}"
        except Exception as e:
            return f"Error extracting text: {e}"

    async def tool_browser_close(self) -> str:
        try:
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            self.page = None
            return "Browser closed."
        except Exception as e:
            return f"Error closing browser: {e}"

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "browser_goto",
                    "description": "Navigates the browser to a specific URL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "The URL to navigate to (must include http/https)."}
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_click",
                    "description": "Clicks an element on the webpage using a CSS selector.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "selector": {"type": "string", "description": "CSS selector for the element to click."}
                        },
                        "required": ["selector"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_type",
                    "description": "Fills an input field on the webpage with text.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "selector": {"type": "string", "description": "CSS selector for the input element."},
                            "text": {"type": "string", "description": "The text to type into the field."}
                        },
                        "required": ["selector", "text"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_screenshot",
                    "description": "Takes a screenshot of the current webpage and saves it to the workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string", "description": "The filename to save the screenshot as (e.g. page.png)."}
                        },
                        "required": ["filename"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_extract_text",
                    "description": "Extracts the visible text from the current webpage.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_close",
                    "description": "Closes the browser session and frees resources.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        ]
