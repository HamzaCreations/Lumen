#!/usr/bin/env python3
"""Capture screenshots of the RAG frontend's key functions using the system Chrome."""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots"
OUT.mkdir(exist_ok=True)

URL = "http://127.0.0.1:5173/"

NAV = {
    "home": "Home",
    "chat": "Chat with Documents",
    "upload": "Upload Documents",
    "library": "Document Library",
    "settings": "Settings",
}


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=True,
            args=[
                "--no-proxy-server",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--force-color-profile=srgb",
                "--hide-scrollbars",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        page = context.new_page()
        page.set_default_timeout(60000)

        print("-> loading", URL)
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(1200)

        def click_nav(name):
            page.locator(".nav-item", has_text=name).first.click()
            page.wait_for_timeout(900)

        # 1. Home
        page.screenshot(path=str(OUT / "home.png"))
        print("saved home.png")

        # 2. Chat with a real question + streamed answer
        click_nav(NAV["chat"])
        page.locator("button.starter", has_text="What is precision?").first.click()
        page.wait_for_timeout(400)
        page.click('button[aria-label="Send question"]')
        # wait until the answer finishes (copy actions appear)
        page.wait_for_selector(".message-actions", timeout=60000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "chat.png"), full_page=True)
        print("saved chat.png")

        # 3. Upload Documents
        click_nav(NAV["upload"])
        page.screenshot(path=str(OUT / "upload.png"))
        print("saved upload.png")

        # 4. Document Library
        click_nav(NAV["library"])
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "library.png"))
        print("saved library.png")

        # 5. Settings
        click_nav(NAV["settings"])
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / "settings.png"))
        print("saved settings.png")

        browser.close()
    print("DONE")


if __name__ == "__main__":
    main()
