import json
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from app.products.scraper.crawler import NaverCafeCrawler

def main():
    crawler = NaverCafeCrawler(
        chrome_profile_path=os.path.join(os.getcwd(), "sessions", "event"),
        debug_mode=True
    )
    
    # Initialize the driver
    crawler.start_browser()
    
    try:
        board_url = "https://cafe.naver.com/ArticleList.nhn?search.clubid=12412554&search.boardtype=L"
        start_date = datetime(2026, 5, 1)
        end_date = datetime(2026, 5, 31)
        
        print(f"Scraping {board_url} from {start_date} to {end_date}")
        articles, is_finished = crawler.scrape_board_list(
            board_url=board_url,
            start_date=start_date,
            end_date=end_date,
            start_page=1,
            max_pages=5
        )
        
        print(f"Scrape completed. is_finished={is_finished}")
        print(f"Collected {len(articles)} articles:")
        for idx, art in enumerate(articles):
            print(f"{idx+1}: ID={art['post_id']}, Date={art['date']}, Title={art['title']}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if crawler.driver:
            crawler.driver.quit()

if __name__ == "__main__":
    main()
