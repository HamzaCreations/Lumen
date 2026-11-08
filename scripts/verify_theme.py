#!/usr/bin/env python3
"""Verify light/dark theme: render, toggle, persist, and screenshot both modes."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots"
OUT.mkdir(exist_ok=True)
URL = "http://127.0.0.1:5173/"

NAV = {"home": "Home", "chat": "Chat with Documents",
       "library": "Document Library", "settings": "Settings"}

def nav(page, name):
    page.locator(".nav-item", has_text=name).first.click()
    page.wait_for_timeout(700)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True,
        args=["--no-proxy-server", "--disable-gpu", "--force-color-profile=srgb",
              "--hide-scrollbars"])
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              device_scale_factor=2)
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(1000)

    def theme():
        return page.evaluate("document.documentElement.getAttribute('data-theme')")

    applied0 = theme()
    print("initial data-theme:", applied0)
    page.screenshot(path=str(OUT / "theme-light-home.png"))
    nav(page, "chat")
    page.screenshot(path=str(OUT / "theme-light-chat.png"))

    # toggle to dark
    page.click(".theme-toggle")
    page.wait_for_timeout(500)
    applied1 = theme()
    stored = page.evaluate("localStorage.getItem('rag:theme')")
    print("after toggle data-theme:", applied1, "| localStorage:", stored)
    page.screenshot(path=str(OUT / "theme-dark-home.png"))
    nav(page, "chat")
    page.screenshot(path=str(OUT / "theme-dark-chat.png"))
    nav(page, "library")
    page.screenshot(path=str(OUT / "theme-dark-library.png"))
    nav(page, "settings")
    page.screenshot(path=str(OUT / "theme-dark-settings.png"))

    # toggle back to light and verify again
    page.click(".theme-toggle")
    page.wait_for_timeout(400)
    print("after second toggle data-theme:", theme(), "| localStorage:",
          page.evaluate("localStorage.getItem('rag:theme')"))

    # persistence across reload
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(800)
    print("after reload data-theme:", theme(), "| localStorage:",
          page.evaluate("localStorage.getItem('rag:theme')"))

    # accessibility check
    label = page.get_attribute(".theme-toggle", "aria-label")
    pressed = page.get_attribute(".theme-toggle", "aria-pressed")
    print("toggle aria-label:", label, "| aria-pressed:", pressed)

    browser.close()
print("DONE")
