from __future__ import annotations

class NaverScraper:
	"""Skeleton for Naver Cafe scraper. Implementation will use Playwright.

	Methods will manage manual login, cookie persistence, and scraping of a single
	article including comments and images converted to base64 for CSV embedding.
	"""

	def __init__(self, sessions_dir: str, snapshots_dir: str) -> None:
		self.sessions_dir = sessions_dir
		self.snapshots_dir = snapshots_dir

	async def ensure_logged_in(self) -> None:
		raise NotImplementedError("Login flow will be implemented with Playwright")

	async def scrape_article(self, url: str, include_nicks: list[str] | None, exclude_nicks: list[str] | None):
		raise NotImplementedError("Article scraping to be implemented next")

