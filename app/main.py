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
	# Placeholder: The actual implementation will open a real browser window
	# for manual login and then save cookies to SESSIONS_DIR.
	return JSONResponse({
		"status": "pending",
		"message": "Manual login flow will open a browser in the next step.",
		"sessions_dir": SESSIONS_DIR,
	})


@app.post("/scrape/article")
async def scrape_single_article(payload: ScrapeArticlePayload) -> JSONResponse:
	if NaverScraper is None:
		return JSONResponse(status_code=501, content={"error": "Scraper not initialized"})

	# Initialize scraper and perform scrape (implementation filled later)
	# Keeping the interface stable for the UI to integrate.
	result = {
		"cafe_id": payload.cafe_id or "unknown",
		"article_id": "",
		"article_url": payload.url,
		"title": "",
		"author_nickname": "",
		"posted_at": None,
		"content_text": "",
		"content_html": "",
		"images_base64": [],
		"comments": [],
	}

	csv_path = append_article_bundle_row(OUTPUTS_DIR, result)
	return JSONResponse({"saved_csv": csv_path, "result_stub": True})

