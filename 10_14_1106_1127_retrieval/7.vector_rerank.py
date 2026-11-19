import os
import runpy
from pathlib import Path

import requests
from elasticsearch import Elasticsearch

def rerank(question, hits):
    if not hits:
        return []

    rerank_response = requests.post(
        "https://labiv-llm.z.cs.kookmin.ac.kr/v1/rerank",
        auth=(os.environ["LABIV_API_ID"], os.environ["LABIV_API_PASSWORD"]),
        json={
            "model": "bge-reranker-v2-m3",
            "query": question,
            "documents": [
                f"{hit['_source']['title']}\n{hit['_source']['text']}"
                for hit in hits
            ],
            "top_n": len(hits),
        },
        timeout=60,
    )
    rerank_response.raise_for_status()
    return rerank_response.json()["results"]


def main():
    rrf = runpy.run_path(str(Path(__file__).with_name("7.rrf.py")))
    args = rrf["parse_args"]()

    with Elasticsearch(
        "https://localhost:9200",
        basic_auth=("elastic", os.environ["ES_PASSWORD"]),
        verify_certs=False,
        ssl_show_warn=False,
    ) as client:
        bm25_hits = rrf["search_bm25"](client, args.question)
        query_vector = rrf["embed_question"](args.question)
        knn_hits = rrf["search_knn"](client, query_vector)

    fused_hits = rrf["reciprocal_rank_fusion"](
        bm25_hits, knn_hits, bm25_weight=args.bm25_weight, knn_weight=args.knn_weight
    )
    hits = fused_hits[:rrf["TOP_K"]]
    rrf["print_results"]("RRF 결과", hits)

    if not hits:
        return

    results = rerank(args.question, hits)

    print("\n리랭킹 결과")
    for rank, result in enumerate(results, start=1):
        original_index = result["index"]
        hit = hits[original_index]
        score = result["relevance_score"]
        print(
            f"{rank}위 (RRF {original_index + 1}위) "
            f"{hit['_id']} {hit['_source']['title']} 관련도: {score:.4f}"
        )
        print(hit["_source"]["text"])


if __name__ == "__main__":
    main()
