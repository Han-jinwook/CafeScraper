import csv
import os
from datetime import datetime
import orjson
from typing import Any, Dict

CSV_FIELDS = [
	"cafe_id",
	"article_id",
	"article_url",
	"title",
	"author_nickname",
	"posted_at",
	"content_text",
	"content_html",
	"images_base64_json",
	"comments_json",
	"scraped_at",
]


def _ensure_today_output_dir(base_dir: str) -> str:
	date_dir = datetime.now().strftime("%Y-%m-%d")
	target = os.path.join(base_dir, date_dir)
	os.makedirs(target, exist_ok=True)
	return target


def append_article_bundle_row(base_dir: str, bundle: Dict[str, Any]) -> str:
	out_dir = _ensure_today_output_dir(base_dir)
	csv_name = datetime.now().strftime("articles_%Y%m%d.csv")
	csv_path = os.path.join(out_dir, csv_name)

	row = {
		"cafe_id": bundle.get("cafe_id", ""),
		"article_id": bundle.get("article_id", ""),
		"article_url": bundle.get("article_url", ""),
		"title": bundle.get("title", ""),
		"author_nickname": bundle.get("author_nickname", ""),
		"posted_at": bundle.get("posted_at") or "",
		"content_text": bundle.get("content_text", ""),
		"content_html": bundle.get("content_html", ""),
		"images_base64_json": orjson.dumps(bundle.get("images_base64", [])).decode(),
		"comments_json": orjson.dumps(bundle.get("comments", [])).decode(),
		"scraped_at": datetime.now().astimezone().isoformat(timespec="seconds"),
	}

	file_exists = os.path.exists(csv_path)
	with open(csv_path, "a", encoding="utf-8", newline="") as f:
		writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
		if not file_exists:
			writer.writeheader()
		writer.writerow(row)
	return csv_path

