import argparse
import os

import requests
from elasticsearch import Elasticsearch

MODEL = "bge-m3"
INDEX = "rag-miracl-ko-bge-m3"
EMBEDDINGS_URL = "https://labiv-llm.z.cs.kookmin.ac.kr/v1/embeddings"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default="혼다 미나코의 출생 병원은 어디인가요?")
    parser.add_argument("--index", default=INDEX)
    args = parser.parse_args()

    embedding_response = requests.post(
        EMBEDDINGS_URL,
        auth=(os.environ["LABIV_API_ID"], os.environ["LABIV_API_PASSWORD"]),
        json={"model": MODEL, "input": args.question},
        timeout=60,
    )
    embedding_response.raise_for_status()
    query_vector = embedding_response.json()["data"][0]["embedding"]

    with Elasticsearch(
        "https://localhost:9200",
        basic_auth=("elastic", os.environ["ES_PASSWORD"]),
        verify_certs=False,
        ssl_show_warn=False,
    ) as client:
        response = client.search(
            index=args.index,
            body={
                "knn": {
                    "field": "embedding",
                    "query_vector": query_vector,
                    "k": 5,
                    "num_candidates": 50,
                },
                "size": 5,
                "_source": ["title", "text"],
            },
        )

    for rank, hit in enumerate(response["hits"]["hits"], start=1):
        print(
            f"{rank}위 {hit['_id']} {hit['_source']['title']} "
            f"점수: {hit['_score']:.6f}"
        )
        print(hit["_source"]["text"])


if __name__ == "__main__":
    main()
