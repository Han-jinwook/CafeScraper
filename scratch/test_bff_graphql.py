import requests
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

club_id = '14358379'
cafe_name = 'campingfirst'

headers = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': f'https://cafe.naver.com/{cafe_name}',
    'Origin': 'https://cafe.naver.com'
}

# Try various cafe-related GraphQL queries
queries = [
    {"label": "introduction by cafeUrl", "query": """
query {
  introduction(cafeUrl: "campingfirst") {
    manager { memberKey nickName }
    staffs { memberKey nickName }
  }
}
"""},
    {"label": "introduction by clubId", "query": """
query {
  introduction(clubId: "14358379") {
    manager { memberKey nickName }
    staffs { memberKey nickName }
  }
}
"""},
    {"label": "cafeIntroduction", "query": """
query {
  cafeIntroduction(cafeId: "14358379") {
    manager { memberKey nickName }
  }
}
"""},
    {"label": "cafe query", "query": """
query {
  cafe(cafeId: "14358379") {
    introduction {
      manager { memberKey }
    }
  }
}
"""},
    {"label": "memberList query", "query": """
query {
  memberList(cafeId: "14358379", grade: "MANAGER") {
    memberKey
    nickName
  }
}
"""},
    {"label": "__schema types introspection", "query": """
query {
  __schema {
    types {
      name
      kind
    }
  }
}
"""},
]

for item in queries:
    print(f"\n=== {item['label']} ===")
    try:
        r = requests.post('https://bff.cafe.naver.com/graphql', 
                          json={'query': item['query']}, 
                          headers=headers, timeout=10)
        print(f"Status: {r.status_code}")
        print(r.text[:800])
    except Exception as e:
        print(f"Error: {e}")
