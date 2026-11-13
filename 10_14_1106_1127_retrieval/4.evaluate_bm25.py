import json
from pathlib import Path

INDEX = "rag-miracl-ko-bm25"
DATASET = Path(__file__).resolve().parent / "dataset"
QUERY_ID = "1192"


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
        "size": 10,
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


def print_first_relevant(ranked_ids, judgments):
    for rank, docid in enumerate(ranked_ids, start=1):
        if judgments.get(docid, 0) >= 1:
            print(f"정답 순위 | {rank}위 ({docid})")
            return
    print("상위 10건에 정답 문단 없음")


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
        print_first_relevant(ranked_ids, judgments)


if __name__ == "__main__":
    main()
