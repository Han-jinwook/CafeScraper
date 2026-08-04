import sys, time
sys.path.append('.')
from app.products.scraper.crawler import NaverCafeCrawler
from selenium.webdriver.common.by import By

c = NaverCafeCrawler()
c.start_browser()
board_url = 'https://cafe.naver.com/ArticleList.nhn?search.clubid=27870803&search.boardtype=L'
page_url = c._build_board_page_url(board_url, 1, user_display=50)
print('Generated URL:', page_url)

c.driver.get('https://cafe.naver.com/sundreamd')
time.sleep(3)
c._switch_to_cafe_iframe()
c.driver.execute_script('location.href = arguments[0];', page_url)
time.sleep(3)
c._switch_to_cafe_iframe()
rows = c.driver.find_elements(By.CSS_SELECTOR, "div[class*='ArticleItem'], li[class*='article'], div.article-board table tbody tr")
print('Rows found:', len(rows))
for i, row in enumerate(rows):
    try:
        is_notice = False
        img_icon = row.find_elements(By.CSS_SELECTOR, "img.list_icon")
        if img_icon:
            src = str(img_icon[0].get_attribute("src") or "")
            if "ico_notice" in src or "ico_mustread" in src:
                is_notice = True
        notice_texts = row.find_elements(By.CSS_SELECTOR, ".board-tag-txt, .badge_notice, .txt_notice")
        for nt in notice_texts:
            nt_txt = str(nt.text or "").strip()
            if "공지" in nt_txt or "필독" in nt_txt:
                is_notice = True
                break
        
        a_tags = row.find_elements(By.CSS_SELECTOR, "a.article, a.tit, a.title, .board-list a")
        if not a_tags: continue
        href = a_tags[0].get_attribute("href")
        date_tds = row.find_elements(By.CSS_SELECTOR, "td.td_date, .date, .time")
        if not date_tds: continue
        date_str = date_tds[0].text.strip()
        print(f"Row {i} [Notice:{is_notice}]: {date_str} - {href}")
    except Exception as e:
        pass
c.driver.quit()
