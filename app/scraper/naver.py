from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from typing import Optional

class NaverScraper:
	"""Naver Cafe scraper with manual login and cookie persistence."""

	def __init__(self, sessions_dir: str, snapshots_dir: str) -> None:
		self.sessions_dir = Path(sessions_dir)
		self.snapshots_dir = Path(snapshots_dir)
		self.sessions_dir.mkdir(exist_ok=True)
		self.snapshots_dir.mkdir(exist_ok=True)
		
		self.browser: Optional[Browser] = None
		self.context: Optional[BrowserContext] = None
		self.page: Optional[Page] = None
		
		self._cookie_file = self.sessions_dir / "naver_cookies.json"

	async def start_browser(self) -> None:
		"""Start browser with persistent context for cookie management."""
		playwright = await async_playwright().start()
		
		# Use persistent context to maintain cookies
		self.context = await playwright.chromium.launch_persistent_context(
			user_data_dir=str(self.sessions_dir / "browser_data"),
			headless=False,  # Show browser for manual login
			args=[
				"--disable-blink-features=AutomationControlled",
				"--disable-web-security",
				"--disable-features=VizDisplayCompositor"
			]
		)
		
		self.browser = self.context.browser
		self.page = await self.context.new_page()
		
		# Load existing cookies if available
		await self._load_cookies()

	async def _load_cookies(self) -> None:
		"""Load saved cookies from file."""
		if self._cookie_file.exists() and self.page:
			try:
				with open(self._cookie_file, 'r', encoding='utf-8') as f:
					cookies = json.load(f)
				await self.context.add_cookies(cookies)
				print(f"✅ Loaded {len(cookies)} cookies from {self._cookie_file}")
			except Exception as e:
				print(f"⚠️ Failed to load cookies: {e}")

	async def _save_cookies(self) -> None:
		"""Save current cookies to file."""
		if self.context:
			try:
				cookies = await self.context.cookies()
				with open(self._cookie_file, 'w', encoding='utf-8') as f:
					json.dump(cookies, f, ensure_ascii=False, indent=2)
				print(f"✅ Saved {len(cookies)} cookies to {self._cookie_file}")
			except Exception as e:
				print(f"⚠️ Failed to save cookies: {e}")

	async def ensure_logged_in(self) -> bool:
		"""Ensure user is logged in to Naver. Returns True if successful."""
		if not self.page:
			await self.start_browser()
		
		# Check if already logged in
		await self.page.goto("https://www.naver.com")
		await self.page.wait_for_load_state("networkidle")
		
		# Look for login indicators
		login_indicators = [
			"text=로그인",
			"text=내정보",
			"[data-clk='log_off.login']",
			".MyView-module__link_login___HpHMW"
		]
		
		is_logged_in = False
		for indicator in login_indicators:
			try:
				element = await self.page.wait_for_selector(indicator, timeout=3000)
				if element and "로그인" not in await element.text_content():
					is_logged_in = True
					break
			except:
				continue
		
		if is_logged_in:
			print("✅ Already logged in to Naver")
			await self._save_cookies()
			return True
		
		# Manual login required
		print("🔐 Manual login required. Please log in to Naver in the browser window.")
		print("   After logging in, press Enter in this terminal to continue...")
		
		# Wait for user to complete login
		input("Press Enter after completing login...")
		
		# Verify login and save cookies
		await self.page.reload()
		await self.page.wait_for_load_state("networkidle")
		
		# Check login status again
		for indicator in login_indicators:
			try:
				element = await self.page.wait_for_selector(indicator, timeout=3000)
				if element and "로그인" not in await element.text_content():
					await self._save_cookies()
					print("✅ Login successful! Cookies saved.")
					return True
			except:
				continue
		
		print("❌ Login verification failed. Please try again.")
		return False

	async def scrape_article(self, url: str, include_nicks: list[str] | None = None, exclude_nicks: list[str] | None = None):
		"""Scrape a single article with comments and images."""
		if not await self.ensure_logged_in():
			raise Exception("Login required but failed")
		
		# Navigate to article
		await self.page.goto(url)
		await self.page.wait_for_load_state("networkidle")
		
		# Take snapshot for debugging
		snapshot_dir = self.snapshots_dir / Path(url).stem
		snapshot_dir.mkdir(exist_ok=True)
		await self.page.screenshot(path=snapshot_dir / "page.png")
		
		# TODO: Implement article scraping logic
		# This will be implemented in the next step
		pass

	async def close(self) -> None:
		"""Close browser and save cookies."""
		if self.context:
			await self._save_cookies()
			await self.context.close()
		print("🔒 Browser closed, cookies saved.")

