import os
from math import hypot, sumprod

import requests

base_url = "https://labiv-llm.z.cs.kookmin.ac.kr"
ID = os.environ["LABIV_API_ID"]
PASSWORD = os.environ["LABIV_API_PASSWORD"]

original = "난 얼죽아야."
rewritten = "난 날씨가 추워도 아이스 아메리카노를 마셔."
reference = "한겨울에도 따뜻한 커피보다 아이스 아메리카노를 고른다."
sentences = [original, rewritten, reference]


def cosine_similarity(left, right):
    dot_product = sumprod(left, right)
    return dot_product / (hypot(*left) * hypot(*right))


path = "/v1/tokenize"
for sentence in sentences:
    payload = {"model": "bge-m3", "content": sentence, "with_pieces": True}
    response = requests.post(
        f"{base_url}{path}", auth=(ID, PASSWORD), json=payload, timeout=60
    )
    response.raise_for_status()
    print(f"\n토큰화: {sentence}")
    pieces = [token["piece"] for token in response.json()["tokens"]]
    print(pieces)

path = "/v1/embeddings"
payload = {"model": "bge-m3", "input": sentences}
response = requests.post(
    f"{base_url}{path}", auth=(ID, PASSWORD), json=payload, timeout=60
)
response.raise_for_status()
vectors = {item["index"]: item["embedding"] for item in response.json()["data"]}

print("\n코사인 유사도")
print(f"원문 ↔ 풀어 쓴 문장: {cosine_similarity(vectors[0], vectors[1]):.4f}")
print(f"원문 ↔ 기준 문장: {cosine_similarity(vectors[0], vectors[2]):.4f}")
print(f"풀어 쓴 문장 ↔ 기준 문장: {cosine_similarity(vectors[1], vectors[2]):.4f}")
