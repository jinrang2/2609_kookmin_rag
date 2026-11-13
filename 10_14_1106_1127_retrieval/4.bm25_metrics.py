import json
from math import log2
from pathlib import Path

INDEX = "rag-miracl-ko-bm25"
DATASET = Path(__file__).resolve().parent / "dataset"
QUERY_ID = "1192"
TOP_K = 10


def read_jsonl(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def read_judgments(path):
    return {
        row["docid"]: row["relevance"]
        for row in read_jsonl(path)
        if row["query_id"] == QUERY_ID
    }


def search(client, question):
    body = {
        "size": TOP_K,
        "_source": ["title", "text"],
        "query": {
            "multi_match": {
                "query": question,
                "fields": ["title", "text"],
                "analyzer": "korean_text",
            }
        },
    }
    response = client.search(index=INDEX, body=body, allow_partial_search_results=False)
    return [hit["_id"] for hit in response["hits"]["hits"]]


def dcg(grades):
    return sum(grade / log2(rank + 1) for rank, grade in enumerate(grades, start=1))


def recall_score(relevant_found, relevant_total):
    if relevant_total == 0:
        return 0.0
    return relevant_found / relevant_total


def reciprocal_rank_score(first_rank):
    if first_rank is None:
        return 0.0
    return 1 / first_rank


def ndcg_score(grades, all_grades):
    ideal_grades = sorted(all_grades, reverse=True)[:TOP_K]
    ideal_dcg = dcg(ideal_grades)
    if ideal_dcg == 0:
        return 0.0
    return dcg(grades) / ideal_dcg


def print_evaluation(ranked_ids, judgments):
    ranked_ids = ranked_ids[:TOP_K]
    grades = [judgments.get(docid, 0) for docid in ranked_ids]
    relevant_ranks = [rank for rank, grade in enumerate(grades, start=1) if grade >= 1]
    first_rank = relevant_ranks[0] if relevant_ranks else None
    if first_rank is not None:
        print(f"정답 순위 | {first_rank}위 ({ranked_ids[first_rank - 1]})")
    else:
        print(f"상위 {TOP_K}건에 정답 문단 없음")

    relevant_total = sum(grade >= 1 for grade in judgments.values())
    recall = recall_score(len(relevant_ranks), relevant_total)
    reciprocal_rank = reciprocal_rank_score(first_rank)
    ndcg = ndcg_score(grades, judgments.values())

    print(f"Recall@{TOP_K} | {recall:.4f}")
    print(f"RR@{TOP_K}     | {reciprocal_rank:.4f}")
    print(f"nDCG@{TOP_K}   | {ndcg:.4f}")


def main():
    question = next(row["text"] for row in read_jsonl(DATASET / "queries.jsonl")
                    if row["query_id"] == QUERY_ID)
    judgments = read_judgments(DATASET / "qrels.jsonl")

    from elasticsearch import Elasticsearch

    print(f"질문 {QUERY_ID} | {question}")
    with Elasticsearch(
        "https://localhost:9200",
        basic_auth=("elastic", "elastic"),
        verify_certs=False,
        ssl_show_warn=False,
    ) as client:
        ranked_ids = search(client, question)
        print_evaluation(ranked_ids, judgments)


if __name__ == "__main__":
    main()
