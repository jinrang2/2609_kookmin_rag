# /// script
# requires-python = ">=3.12"
# dependencies = ["elasticsearch>=8.19,<8.20"]
# ///
"""Elasticsearch 8.19 접속 확인과 검색 예제.

학생용 저장소 루트에서 실행:
    uv run --script ./07_1023_integrated_lab/es.py

"""

import json
from elasticsearch import Elasticsearch


# 1. 주소, 사용자 이름, 비밀번호를 수업에서 받은 값으로 바꾸세요.
es = Elasticsearch(
    "https://localhost:9200",
    basic_auth=("elastic", "YOUR_PASSWORD"),
    verify_certs=False,
    ssl_show_warn=False,
)

# 2. 접속 확인
info = es.info()
print("클러스터:", info["cluster_name"])
print("서버 버전:", info["version"]["number"])

# 3. 검색: query를 바꾸면서 연습문제를 풉니다.
query = {"match_all": {}}
response = es.search(
    index="kibana_sample_data_ecommerce",
    query=query,
    size=10,
    track_total_hits=True,
)

print("조건에 맞는 전체 주문 수:", response["hits"]["total"]["value"])
print("이번에 가져온 주문 수:", len(response["hits"]["hits"]))

# 4. 검색 결과 출력
for hit in response["hits"]["hits"]:
    print("\n문서 ID:", hit["_id"])
    print(json.dumps(hit["_source"], ensure_ascii=False, indent=2))

es.close()
