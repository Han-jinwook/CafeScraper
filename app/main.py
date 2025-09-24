import os
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Lazy imports for optional heavy deps
try:
	from app.scraper.naver import NaverScraper
except Exception:
	NaverScraper = None  # type: ignore

from app.utils.csv_writer import append_article_bundle_row

app = FastAPI(title="CafeScraper", version="0.1.0")

SESSIONS_DIR = os.path.abspath(os.path.join(os.getcwd(), "sessions"))
OUTPUTS_DIR = os.path.abspath(os.path.join(os.getcwd(), "outputs"))
SNAPSHOTS_DIR = os.path.abspath(os.path.join(os.getcwd(), "snapshots"))

for _d in (SESSIONS_DIR, OUTPUTS_DIR, SNAPSHOTS_DIR):
	os.makedirs(_d, exist_ok=True)


class CommentFilter(BaseModel):
	include: list[str] | None = None
	exclude: list[str] | None = None


class ScrapeArticlePayload(BaseModel):
	url: str
	cafe_id: str | None = None
	comment_filter: CommentFilter | None = None


@app.get("/health")
async def health() -> dict:
	return {"ok": True}


@app.post("/login/start")
async def login_start() -> JSONResponse:
	"""Start manual login process with browser window."""
	try:
		scraper = NaverScraper(SESSIONS_DIR, SNAPSHOTS_DIR)
		success = await scraper.ensure_logged_in()
		await scraper.close()
		
		if success:
			return JSONResponse({
				"status": "success",
				"message": "Login completed successfully. Cookies saved.",
				"sessions_dir": str(SESSIONS_DIR),
			})
		else:
			return JSONResponse({
				"status": "failed", 
				"message": "Login failed. Please try again.",
				"sessions_dir": str(SESSIONS_DIR),
			})
	except Exception as e:
		return JSONResponse({
			"status": "error",
			"message": f"Login error: {str(e)}",
			"sessions_dir": str(SESSIONS_DIR),
		}, status_code=500)


@app.post("/scrape/article")
async def scrape_single_article(payload: ScrapeArticlePayload) -> JSONResponse:
	"""Scrape a single article with comments and images."""
	try:
		scraper = NaverScraper(SESSIONS_DIR, SNAPSHOTS_DIR)
		
		# Extract comment filters
		include_nicks = payload.comment_filter.include if payload.comment_filter else None
		exclude_nicks = payload.comment_filter.exclude if payload.comment_filter else None
		
		# TODO: Implement actual scraping logic
		# For now, return a placeholder result
		result = {
			"cafe_id": payload.cafe_id or "unknown",
			"article_id": "placeholder",
			"article_url": payload.url,
			"title": "Placeholder Title",
			"author_nickname": "Placeholder Author",
			"posted_at": None,
			"content_text": "Placeholder content",
			"content_html": "<p>Placeholder content</p>",
			"images_base64": [],
			"comments": [],
		}

		csv_path = append_article_bundle_row(OUTPUTS_DIR, result)
		await scraper.close()
		
		return JSONResponse({
			"status": "success",
			"saved_csv": csv_path,
			"message": "Article scraped and saved to CSV",
			"result": result
		})
		
	except Exception as e:
		return JSONResponse({
			"status": "error",
			"message": f"Scraping failed: {str(e)}",
		}, status_code=500)

