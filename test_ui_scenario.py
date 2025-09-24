#!/usr/bin/env python3
"""
UI 시나리오 테스트 스크립트
사용자가 UI에서 입력할 수 있는 모든 옵션을 시뮬레이션
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add app directory to path
sys.path.append(str(Path(__file__).parent))

from app.scraper.naver import NaverScraper
from app.utils.csv_writer import append_article_bundle_row

class UIScenarioTester:
    """UI 시나리오를 시뮬레이션하는 테스트 클래스"""
    
    def __init__(self):
        self.sessions_dir = Path("sessions")
        self.snapshots_dir = Path("snapshots")
        self.outputs_dir = Path("outputs")
        
        # UI에서 사용자가 선택할 수 있는 옵션들
        self.cafe_options = {
            "1": {"id": "sundreamd", "name": "썬드림D치료일기", "url": "https://cafe.naver.com/sundreamd"},
            "2": {"id": "healingcafe", "name": "치유카페", "url": "https://cafe.naver.com/healingcafe"},
            "3": {"id": "wellness", "name": "웰니스카페", "url": "https://cafe.naver.com/wellness"}
        }
        
        # 카페별 게시판(메뉴) 정보
        self.board_options = {
            "sundreamd": {
                "1": {"id": "all", "name": "전체 게시판", "url": "https://cafe.naver.com/sundreamd"},
                "2": {"id": "free", "name": "자유게시판", "url": "https://cafe.naver.com/sundreamd/FreeBoard"},
                "3": {"id": "healing", "name": "치유일기", "url": "https://cafe.naver.com/sundreamd/HealingDiary"},
                "4": {"id": "qna", "name": "질문답변", "url": "https://cafe.naver.com/sundreamd/QnA"},
                "5": {"id": "info", "name": "정보공유", "url": "https://cafe.naver.com/sundreamd/Info"}
            },
            "healingcafe": {
                "1": {"id": "all", "name": "전체 게시판", "url": "https://cafe.naver.com/healingcafe"},
                "2": {"id": "daily", "name": "일상공유", "url": "https://cafe.naver.com/healingcafe/Daily"},
                "3": {"id": "therapy", "name": "치료후기", "url": "https://cafe.naver.com/healingcafe/Therapy"}
            }
        }
        
        self.test_scenarios = [
            {
                "name": "전체 게시판 수집",
                "cafe_id": "sundreamd",
                "board_ids": ["all"],  # 전체 게시판
                "filters": {
                    "date_range": {"start": "2025-01-01", "end": "2025-12-31"},
                    "author_nicknames": [],
                    "comment_nicknames": ["멀린", "큐레이터"],
                    "title_keywords": [],
                    "content_keywords": []
                }
            },
            {
                "name": "치유일기 게시판만",
                "cafe_id": "sundreamd",
                "board_ids": ["healing"],  # 치유일기 게시판만
                "filters": {
                    "date_range": {"start": "2025-01-01", "end": "2025-12-31"},
                    "author_nicknames": ["치유사", "힐러"],
                    "comment_nicknames": ["멀린"],
                    "title_keywords": ["치유", "일기"],
                    "content_keywords": ["증상", "개선"]
                }
            },
            {
                "name": "여러 게시판 수집",
                "cafe_id": "sundreamd",
                "board_ids": ["healing", "qna", "info"],  # 치유일기 + 질문답변 + 정보공유
                "filters": {
                    "date_range": {"start": "2025-01-01", "end": "2025-12-31"},
                    "author_nicknames": [],
                    "comment_nicknames": ["멀린"],
                    "title_keywords": ["치유"],
                    "content_keywords": []
                }
            }
        ]

    async def run_scenario(self, scenario):
        """특정 시나리오 실행"""
        print(f"\n🎭 시나리오: {scenario['name']}")
        print(f"📝 카페: {scenario['cafe_id']}")
        print(f"📚 게시판: {', '.join(scenario['board_ids'])}")
        print(f"📅 기간: {scenario['filters']['date_range']['start']} ~ {scenario['filters']['date_range']['end']}")
        print(f"👤 작성자 필터: {scenario['filters']['author_nicknames']}")
        print(f"💬 댓글 작성자: {scenario['filters']['comment_nicknames']}")
        print(f"🔍 제목 키워드: {scenario['filters']['title_keywords']}")
        print(f"📄 본문 키워드: {scenario['filters']['content_keywords']}")
        
        scraper = NaverScraper(str(self.sessions_dir), str(self.snapshots_dir))
        
        try:
            # 로그인 확인
            if not await scraper.ensure_logged_in():
                print("❌ 로그인 실패")
                return False
            
            # 게시판별 스크래핑 (시뮬레이션)
            all_results = []
            for board_id in scenario['board_ids']:
                print(f"\n📚 게시판 '{board_id}' 스크래핑 중...")
                
                # 게시판 URL 생성 (시뮬레이션)
                if board_id == "all":
                    board_url = f"https://cafe.naver.com/{scenario['cafe_id']}"
                else:
                    board_url = f"https://cafe.naver.com/{scenario['cafe_id']}/{board_id}"
                
                # 게시판 스크래핑 (현재는 단일 URL로 시뮬레이션)
                result = await scraper.scrape_article(
                    board_url,
                    scenario['filters']['comment_nicknames'],
                    []  # exclude_nicks
                )
                
                # 게시판 정보 추가
                result['board_id'] = board_id
                all_results.append(result)
            
            # 모든 결과를 하나로 합치기
            combined_result = self.combine_results(all_results, scenario)
            
            # CSV 저장
            csv_path = append_article_bundle_row(self.outputs_dir, combined_result)
            print(f"✅ CSV 저장: {csv_path}")
            
            # 결과 요약
            self.print_summary(combined_result)
            
            return True
            
        except Exception as e:
            print(f"❌ 오류: {e}")
            return False
        finally:
            await scraper.close()

    def combine_results(self, all_results, scenario):
        """여러 게시판 결과를 하나로 합치기"""
        if not all_results:
            return {}
        
        # 첫 번째 결과를 기본으로 사용
        combined = all_results[0].copy()
        
        # 게시판 정보 추가
        combined['board_ids'] = scenario['board_ids']
        combined['applied_filters'] = {
            'date_range': scenario['filters']['date_range'],
            'author_nicknames': scenario['filters']['author_nicknames'],
            'comment_nicknames': scenario['filters']['comment_nicknames'],
            'title_keywords': scenario['filters']['title_keywords'],
            'content_keywords': scenario['filters']['content_keywords']
        }
        
        # 여러 게시판에서 수집된 이미지와 댓글 합치기
        all_images = []
        all_comments = []
        
        for result in all_results:
            all_images.extend(result.get('images_base64', []))
            all_comments.extend(result.get('comments', []))
        
        combined['images_base64'] = all_images
        combined['comments'] = all_comments
        
        return combined

    def print_summary(self, result):
        """결과 요약 출력"""
        print(f"\n📊 수집 결과:")
        print(f"  - 카페 ID: {result.get('cafe_id', 'N/A')}")
        print(f"  - 게시판: {', '.join(result.get('board_ids', []))}")
        print(f"  - 게시글 ID: {result.get('article_id', 'N/A')}")
        print(f"  - 제목: {result.get('title', 'N/A')}")
        print(f"  - 작성자: {result.get('author_nickname', 'N/A')}")
        print(f"  - 작성일: {result.get('posted_at', 'N/A')}")
        print(f"  - 이미지 수: {len(result.get('images_base64', []))}")
        print(f"  - 댓글 수: {len(result.get('comments', []))}")
        
        if result.get('applied_filters'):
            filters = result['applied_filters']
            print(f"  - 적용된 필터:")
            print(f"    * 기간: {filters['date_range']['start']} ~ {filters['date_range']['end']}")
            print(f"    * 작성자: {filters['author_nicknames']}")
            print(f"    * 댓글 작성자: {filters['comment_nicknames']}")
            print(f"    * 제목 키워드: {filters['title_keywords']}")
            print(f"    * 본문 키워드: {filters['content_keywords']}")

    async def run_all_scenarios(self):
        """모든 시나리오 실행"""
        print("🚀 UI 시나리오 테스트 시작...")
        print("=" * 50)
        
        success_count = 0
        total_count = len(self.test_scenarios)
        
        for i, scenario in enumerate(self.test_scenarios, 1):
            print(f"\n📋 시나리오 {i}/{total_count}")
            success = await self.run_scenario(scenario)
            if success:
                success_count += 1
            print("-" * 50)
        
        print(f"\n🎯 테스트 완료: {success_count}/{total_count} 성공")
        return success_count == total_count

    def interactive_mode(self):
        """대화형 모드"""
        print("🎮 대화형 UI 시뮬레이션 모드")
        print("=" * 50)
        
        # 카페 선택
        print("\n📚 카페 선택:")
        for key, cafe in self.cafe_options.items():
            print(f"  {key}. {cafe['name']} ({cafe['id']})")
        
        cafe_choice = input("\n카페 번호를 선택하세요 (1-3): ").strip()
        if cafe_choice not in self.cafe_options:
            print("❌ 잘못된 선택")
            return
        
        selected_cafe = self.cafe_options[cafe_choice]
        print(f"✅ 선택된 카페: {selected_cafe['name']}")
        
        # 게시판 선택
        print(f"\n📚 {selected_cafe['name']} 게시판 선택:")
        cafe_boards = self.board_options.get(selected_cafe['id'], {})
        for key, board in cafe_boards.items():
            print(f"  {key}. {board['name']} ({board['id']})")
        
        board_choices = input("\n게시판 번호를 선택하세요 (쉼표로 구분, 예: 1,2,3 또는 Enter로 전체): ").strip()
        if not board_choices:
            board_ids = ["all"]
        else:
            board_ids = []
            for choice in board_choices.split(","):
                choice = choice.strip()
                if choice in cafe_boards:
                    board_ids.append(cafe_boards[choice]['id'])
                else:
                    print(f"⚠️ 잘못된 선택: {choice}")
        
        print(f"✅ 선택된 게시판: {', '.join(board_ids)}")
        
        # 필터 설정
        print("\n🔍 필터 설정:")
        
        # 기간 설정
        start_date = input("시작 날짜 (YYYY-MM-DD, Enter로 기본값): ").strip()
        if not start_date:
            start_date = "2025-01-01"
        
        end_date = input("종료 날짜 (YYYY-MM-DD, Enter로 기본값): ").strip()
        if not end_date:
            end_date = "2025-12-31"
        
        # 작성자 필터
        author_nicks = input("작성자 닉네임 (쉼표로 구분, Enter로 건너뛰기): ").strip()
        author_list = [nick.strip() for nick in author_nicks.split(",")] if author_nicks else []
        
        # 댓글 작성자 필터
        comment_nicks = input("댓글 작성자 닉네임 (쉼표로 구분, Enter로 건너뛰기): ").strip()
        comment_list = [nick.strip() for nick in comment_nicks.split(",")] if comment_nicks else []
        
        # 키워드 필터
        title_keywords = input("제목 키워드 (쉼표로 구분, Enter로 건너뛰기): ").strip()
        title_list = [kw.strip() for kw in title_keywords.split(",")] if title_keywords else []
        
        content_keywords = input("본문 키워드 (쉼표로 구분, Enter로 건너뛰기): ").strip()
        content_list = [kw.strip() for kw in content_keywords.split(",")] if content_keywords else []
        
        # 시나리오 생성
        scenario = {
            "name": "사용자 정의 시나리오",
            "cafe_id": selected_cafe['id'],
            "board_ids": board_ids,
            "filters": {
                "date_range": {"start": start_date, "end": end_date},
                "author_nicknames": author_list,
                "comment_nicknames": comment_list,
                "title_keywords": title_list,
                "content_keywords": content_list
            }
        }
        
        return scenario

async def main():
    """메인 함수"""
    tester = UIScenarioTester()
    
    print("🎯 UI 시나리오 테스트")
    print("1. 모든 시나리오 실행")
    print("2. 대화형 모드")
    print("3. 특정 시나리오 실행")
    
    choice = input("\n선택하세요 (1-3): ").strip()
    
    if choice == "1":
        await tester.run_all_scenarios()
    elif choice == "2":
        scenario = tester.interactive_mode()
        if scenario:
            await tester.run_scenario(scenario)
    elif choice == "3":
        print("\n사용 가능한 시나리오:")
        for i, scenario in enumerate(tester.test_scenarios, 1):
            print(f"  {i}. {scenario['name']}")
        
        try:
            scenario_choice = int(input("시나리오 번호를 선택하세요: ")) - 1
            if 0 <= scenario_choice < len(tester.test_scenarios):
                await tester.run_scenario(tester.test_scenarios[scenario_choice])
            else:
                print("❌ 잘못된 선택")
        except ValueError:
            print("❌ 숫자를 입력하세요")
    else:
        print("❌ 잘못된 선택")

if __name__ == "__main__":
    asyncio.run(main())
