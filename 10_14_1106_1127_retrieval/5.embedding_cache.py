import os
from collections import OrderedDict

import requests

BASE_URL = "https://labiv-llm.z.cs.kookmin.ac.kr"
ID = os.environ["LABIV_API_ID"]
PASSWORD = os.environ["LABIV_API_PASSWORD"]
MODEL = "bge-m3"
MAX_CACHE_SIZE = 128

embedding_cache = OrderedDict()


def embed(text):
    key = (MODEL, text)
    if key in embedding_cache:
        print(f"캐시 적중 · {text}")
        embedding_cache.move_to_end(key)
        return embedding_cache[key]

    print(f"서버 요청 · {text}")
    path = "/v1/embeddings"
    payload = {"model": MODEL, "input": text}
    response = requests.post(
        f"{BASE_URL}{path}", auth=(ID, PASSWORD), json=payload, timeout=60
    )
    response.raise_for_status()
    vector = response.json()["data"][0]["embedding"]
    embedding_cache[key] = vector
    if len(embedding_cache) > MAX_CACHE_SIZE:
        embedding_cache.popitem(last=False)
    return vector


if __name__ == "__main__":
    question = "혼다 미나코의 출생 병원은 어디인가요?"

    first_vector = embed(question)
    second_vector = embed(question)

    print(f"벡터 차원: {len(first_vector)}")
    print(f"두 벡터가 같은가요? {first_vector == second_vector}")
