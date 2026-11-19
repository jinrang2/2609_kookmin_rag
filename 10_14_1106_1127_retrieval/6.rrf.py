import argparse
import math
import os

import requests
from elasticsearch import Elasticsearch

QUESTION = "혼다 미나코의 출생 병원은 어디인가요?"
TOP_K = 10
RANK_CONSTANT = 60


def search_bm25(client, question):
    response = client.search(
        index="rag-miracl-ko-bm25",
        body={
            "size": TOP_K,
            "_source": ["title", "text"],
            "query": {
                "multi_match": {
                    "query": question,
                    "fields": ["title", "text"],
                    "analyzer": "korean_text",
                }
            },
        },
    )
    return response["hits"]["hits"]


def embed_question(question):
    response = requests.post(
        "https://labiv-llm.z.cs.kookmin.ac.kr/v1/embeddings",
        auth=(os.environ["LABIV_API_ID"], os.environ["LABIV_API_PASSWORD"]),
        json={"model": "bge-m3", "input": question},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def search_knn(client, question_vector):
    response = client.search(
        index="rag-miracl-ko-bge-m3-title-body",
        body={
            "size": TOP_K,
            "_source": ["title", "text"],
            "knn": {
                "field": "embedding",
                "query_vector": question_vector,
                "k": TOP_K,
                "num_candidates": 50,
            },
        },
    )
    return response["hits"]["hits"]


def reciprocal_rank_fusion(bm25_hits, knn_hits, *, bm25_weight=1.0, knn_weight=1.0):
    scores = {}
    documents = {}
    for hits, weight in ((bm25_hits, bm25_weight), (knn_hits, knn_weight)):
        if weight == 0:
            continue
        for rank, hit in enumerate(hits, start=1):
            docid = hit["_id"]
            scores[docid] = scores.get(docid, 0.0) + weight / (RANK_CONSTANT + rank)
            documents[docid] = hit["_source"]
    return [
        {"_id": docid, "_score": score, "_source": documents[docid]}
        for docid, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
    ]


def print_results(label, hits):
    print(f"\n{label}")
    for rank, hit in enumerate(hits[:TOP_K], start=1):
        print(
            f"{rank}위 {hit['_id']} {hit['_source']['title']} "
            f"점수: {hit['_score']:.6f}"
        )
        print(hit["_source"]["text"])


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default=QUESTION)
    parser.add_argument("--bm25-weight", type=float, default=1.0)
    parser.add_argument("--knn-weight", type=float, default=1.0)
    args = parser.parse_args()
    weights = (args.bm25_weight, args.knn_weight)
    if any(not math.isfinite(weight) or weight < 0 for weight in weights) or not any(weights):
        parser.error("가중치는 0 이상의 유한한 수여야 하며, 하나 이상은 0보다 커야 합니다.")
    return args


def main():
    args = parse_args()
    with Elasticsearch(
        "https://localhost:9200",
        basic_auth=("elastic", os.environ["ES_PASSWORD"]),
        verify_certs=False,
        ssl_show_warn=False,
    ) as client:
        bm25_hits = search_bm25(client, args.question)
        print_results("BM25", bm25_hits)
        question_vector = embed_question(args.question)
        knn_hits = search_knn(client, question_vector)
        print_results("kNN", knn_hits)

    fused_hits = reciprocal_rank_fusion(
        bm25_hits, knn_hits, bm25_weight=args.bm25_weight, knn_weight=args.knn_weight
    )
    print_results("RRF", fused_hits)


if __name__ == "__main__":
    main()
