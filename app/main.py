import os
import logging
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

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
STATIC_DIR = os.path.abspath(os.path.join(os.getcwd(), "app", "static"))

for _d in (SESSIONS_DIR, OUTPUTS_DIR, SNAPSHOTS_DIR, STATIC_DIR):
	os.makedirs(_d, exist_ok=True)

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class CommentFilter(BaseModel):
	include: list[str] | None = None
	exclude: list[str] | None = None


class ScrapeArticlePayload(BaseModel):
	url: str
	cafe_id: str | None = None
	comment_filter: CommentFilter | None = None


class ScrapeBoardPayload(BaseModel):
	board_url: str
	max_pages: int = 5
	comment_filter: CommentFilter | None = None


class ScrapeMultipleArticlesPayload(BaseModel):
	article_urls: list[str]
	comment_filter: CommentFilter | None = None


class CafeBoardsPayload(BaseModel):
	cafe_url: str
	cafe_name: str | None = None


class CafeScrapingPayload(BaseModel):
	cafe_url: str
	max_pages: int = 5
	all_boards: bool = True
	selected_boards: list[str] = []
	comment_filter: CommentFilter | None = None


class BatchScrapingPayload(BaseModel):
	cafe_url: str
	max_pages: int = 5
	all_boards: bool = True
	selected_boards: list[str] = []
	search_keywords: list[str] = []
	post_authors: list[str] = []
	comment_authors: list[str] = []
	max_articles: int = 1000
	image_processing: str = "base64"  # none, base64, server
	period: str = "all"  # all, 1month, 6months, 1year, custom
	delay_between_requests: int = 3


@app.get("/")
async def root():
	"""웹 UI 홈페이지"""
	return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def chrome_devtools():
	"""Chrome DevTools 메타데이터"""
	return {"version": "1.0", "name": "CafeScraper API"}


@app.get("/favicon.ico")
async def favicon():
	"""파비콘 요청 처리"""
	from fastapi.responses import Response
	return Response(status_code=204)  # No Content

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
		
		# Perform actual scraping
		result = await scraper.scrape_article(
			payload.url, 
			include_nicks, 
			exclude_nicks
		)

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


@app.post("/scrape/board")
async def scrape_board_articles(payload: ScrapeBoardPayload) -> JSONResponse:
	"""Scrape articles from a board page with pagination."""
	try:
		scraper = NaverScraper(SESSIONS_DIR, SNAPSHOTS_DIR)
		
		# Extract comment filters
		include_nicks = payload.comment_filter.include if payload.comment_filter else None
		exclude_nicks = payload.comment_filter.exclude if payload.comment_filter else None
		
		print(f"📊 게시판 스크래핑 시작: {payload.board_url}")
		print(f"📄 최대 페이지: {payload.max_pages}")
		
		# Get article list from board
		articles = await scraper.scrape_board_articles(payload.board_url, payload.max_pages)
		
		if not articles:
			await scraper.close()
			return JSONResponse({
				"status": "warning",
				"message": "No articles found on the board",
				"articles_found": 0,
				"articles_scraped": 0,
				"saved_csvs": [],
				"results": []
			})
		
		# Extract URLs for detailed scraping
		article_urls = [article["article_url"] for article in articles]
		
		print(f"📊 발견된 게시글: {len(article_urls)}개")
		
		# Scrape detailed information for each article
		detailed_results = await scraper.scrape_multiple_articles(article_urls, include_nicks, exclude_nicks)
		
		# Save to CSV
		csv_paths = []
		successful_results = []
		
		for result in detailed_results:
			if "error" not in result:
				csv_path = append_article_bundle_row(OUTPUTS_DIR, result)
				csv_paths.append(csv_path)
				successful_results.append(result)
		
		await scraper.close()
		
		success_count = len(successful_results)
		error_count = len(detailed_results) - success_count
		
		return JSONResponse({
			"status": "success",
			"message": f"Board scraped: {success_count} articles processed successfully, {error_count} errors",
			"articles_found": len(articles),
			"articles_scraped": success_count,
			"articles_failed": error_count,
			"saved_csvs": csv_paths,
			"results": detailed_results
		})
		
	except Exception as e:
		return JSONResponse({
			"status": "error",
			"message": f"Board scraping failed: {str(e)}",
		}, status_code=500)


@app.post("/scrape/multiple")
async def scrape_multiple_articles(payload: ScrapeMultipleArticlesPayload) -> JSONResponse:
	"""Scrape multiple articles from a list of URLs."""
	try:
		scraper = NaverScraper(SESSIONS_DIR, SNAPSHOTS_DIR)
		
		# Extract comment filters
		include_nicks = payload.comment_filter.include if payload.comment_filter else None
		exclude_nicks = payload.comment_filter.exclude if payload.comment_filter else None
		
		# Scrape multiple articles
		results = await scraper.scrape_multiple_articles(payload.article_urls, include_nicks, exclude_nicks)
		
		# Save to CSV
		csv_paths = []
		for result in results:
			csv_path = append_article_bundle_row(OUTPUTS_DIR, result)
			csv_paths.append(csv_path)
		
		await scraper.close()
		
		return JSONResponse({
			"status": "success",
			"message": f"Multiple articles scraped: {len(results)} articles processed",
			"saved_csvs": csv_paths,
			"results": results
		})
		
	except Exception as e:
		return JSONResponse({
			"status": "error",
			"message": f"Multiple articles scraping failed: {str(e)}",
		}, status_code=500)


@app.post("/cafe/boards")
async def get_cafe_boards(payload: CafeBoardsPayload) -> JSONResponse:
	"""카페의 게시판 목록 조회"""
	try:
		print(f"🔄 게시판 목록 조회 시작: {payload.cafe_url}")
		scraper = NaverScraper(SESSIONS_DIR, SNAPSHOTS_DIR)
		
		# 카페 게시판 목록 조회
		boards = await scraper.get_cafe_boards(payload.cafe_url)
		
		await scraper.close()
		
		if not boards:
			return JSONResponse({
				"status": "warning",
				"message": "게시판을 찾을 수 없습니다. 카페 URL을 확인하거나 로그인 상태를 확인하세요.",
				"boards": []
			})
		
		print(f"✅ 게시판 목록 조회 성공: {len(boards)}개")
		return JSONResponse({
			"status": "success",
			"message": f"게시판 목록을 조회했습니다. ({len(boards)}개)",
			"boards": boards
		})
		
	except Exception as e:
		error_msg = str(e)
		print(f"❌ 게시판 목록 조회 실패: {error_msg}")
		
		if "Login required" in error_msg:
			error_msg = "로그인이 필요합니다. 먼저 로그인을 진행하세요."
		elif "NoneType" in error_msg or "Browser" in error_msg:
			error_msg = "브라우저 초기화 오류입니다. 서버를 재시작하세요."
		elif "timeout" in error_msg.lower():
			error_msg = "페이지 로딩 시간 초과입니다. 네트워크 연결을 확인하세요."
		
		return JSONResponse({
			"status": "error",
			"message": f"게시판 목록 조회 실패: {error_msg}",
		}, status_code=500)


@app.post("/scrape/cafe")
async def scrape_cafe(payload: CafeScrapingPayload) -> JSONResponse:
	"""카페 전체 또는 특정 게시판 스크래핑"""
	try:
		scraper = NaverScraper(SESSIONS_DIR, SNAPSHOTS_DIR)
		
		# Extract comment filters
		include_nicks = payload.comment_filter.include if payload.comment_filter else None
		exclude_nicks = payload.comment_filter.exclude if payload.comment_filter else None
		
		print(f"📊 카페 스크래핑 시작: {payload.cafe_url}")
		print(f"📄 전체 게시판: {payload.all_boards}")
		if not payload.all_boards:
			print(f"📄 선택된 게시판: {payload.selected_boards}")
		
		# 카페 스크래핑 실행
		results = await scraper.scrape_cafe(
			payload.cafe_url,
			payload.max_pages,
			payload.all_boards,
			payload.selected_boards,
			include_nicks,
			exclude_nicks
		)
		
		# Save to CSV
		csv_paths = []
		successful_results = []
		
		for result in results:
			if "error" not in result:
				csv_path = append_article_bundle_row(OUTPUTS_DIR, result)
				csv_paths.append(csv_path)
				successful_results.append(result)
		
		await scraper.close()
		
		success_count = len(successful_results)
		error_count = len(results) - success_count
		
		return JSONResponse({
			"status": "success",
			"message": f"카페 스크래핑 완료: {success_count}개 게시글 처리 성공, {error_count}개 실패",
			"articles_scraped": success_count,
			"articles_failed": error_count,
			"saved_csvs": csv_paths,
			"results": results
		})
		
	except Exception as e:
		return JSONResponse({
			"status": "error",
			"message": f"카페 스크래핑 실패: {str(e)}",
		}, status_code=500)


@app.post("/scrape/batch")
async def batch_scraping(payload: BatchScrapingPayload) -> JSONResponse:
	"""배치 크롤링 - 키워드 검색 및 작성자 필터링 포함"""
	try:
		scraper = NaverScraper(SESSIONS_DIR, SNAPSHOTS_DIR)
		
		print(f"🔄 배치 크롤링 시작: {payload.cafe_url}")
		print(f"🔍 키워드: {payload.search_keywords}")
		print(f"👤 게시글 작성자: {payload.post_authors}")
		print(f"💬 댓글 작성자: {payload.comment_authors}")
		print(f"📊 최대 게시글 수: {payload.max_articles}")
		
		# 배치 크롤링 실행
		results = await scraper.batch_scraping(
			payload.cafe_url,
			payload.max_pages,
			payload.all_boards,
			payload.selected_boards,
			payload.search_keywords,
			payload.post_authors,
			payload.comment_authors,
			payload.max_articles,
			payload.image_processing,
			payload.period,
			payload.delay_between_requests
		)
		
		# Save to CSV
		csv_paths = []
		successful_results = []
		
		for result in results:
			if "error" not in result:
				csv_path = append_article_bundle_row(OUTPUTS_DIR, result)
				csv_paths.append(csv_path)
				successful_results.append(result)
		
		await scraper.close()
		
		success_count = len(successful_results)
		error_count = len(results) - success_count
		
		return JSONResponse({
			"status": "success",
			"message": f"배치 크롤링 완료: {success_count}개 게시글 처리 성공, {error_count}개 실패",
			"articles_scraped": success_count,
			"articles_failed": error_count,
			"saved_csvs": csv_paths,
			"results": results
		})
		
	except Exception as e:
		return JSONResponse({
			"status": "error",
			"message": f"배치 크롤링 실패: {str(e)}",
		}, status_code=500)


@app.get("/monitor/status")
async def get_system_status() -> JSONResponse:
	"""시스템 상태 조회"""
	try:
		from app.utils.monitor import performance_monitor
		status = performance_monitor.get_system_status()
		return JSONResponse({
			"status": "success",
			"data": status
		})
	except Exception as e:
		return JSONResponse({
			"status": "error",
			"message": f"시스템 상태 조회 실패: {str(e)}"
		}, status_code=500)


@app.get("/monitor/stats/{date}")
async def get_daily_stats(date: str) -> JSONResponse:
	"""일일 통계 조회"""
	try:
		from app.utils.monitor import performance_monitor
		stats = performance_monitor.get_daily_stats(date)
		return JSONResponse({
			"status": "success",
			"data": stats
		})
	except Exception as e:
		return JSONResponse({
			"status": "error",
			"message": f"통계 조회 실패: {str(e)}"
		}, status_code=500)


@app.get("/monitor/cleanup")
async def cleanup_old_metrics(days: int = 30) -> JSONResponse:
	"""오래된 메트릭 파일 정리"""
	try:
		from app.utils.monitor import performance_monitor
		performance_monitor.cleanup_old_metrics(days)
		return JSONResponse({
			"status": "success",
			"message": f"{days}일 이상 된 메트릭 파일이 정리되었습니다."
		})
	except Exception as e:
		return JSONResponse({
			"status": "error",
			"message": f"메트릭 정리 실패: {str(e)}"
		}, status_code=500)

