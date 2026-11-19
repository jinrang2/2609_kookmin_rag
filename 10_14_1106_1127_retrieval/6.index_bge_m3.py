import json
import os
from pathlib import Path

import requests
from elasticsearch import Elasticsearch, helpers

MODEL = "bge-m3"
INDEX = "rag-miracl-ko-bge-m3"
EMBEDDINGS_URL = "https://labiv-llm.z.cs.kookmin.ac.kr/v1/embeddings"
BATCH_SIZE = 10


def embed(texts):
    response = requests.post(
        EMBEDDINGS_URL,
        auth=(os.environ["LABIV_API_ID"], os.environ["LABIV_API_PASSWORD"]),
        json={"model": MODEL, "input": texts},
        timeout=60,
    )
    response.raise_for_status()
    vectors = {item["index"]: item["embedding"] for item in response.json()["data"]}
    return [vectors[index] for index in range(len(texts))]


def index_passages(client):
    corpus_path = Path(__file__).resolve().parent / "dataset" / "corpus.jsonl"
    with corpus_path.open(encoding="utf-8") as corpus:
        passages = [json.loads(line) for line in corpus if line.strip()]

    if not client.indices.exists(index=INDEX):
        client.indices.create(
            index=INDEX,
            mappings={
                "properties": {
                    "title": {"type": "text"},
                    "text": {"type": "text"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": 1024,
                        "similarity": "cosine",
                    },
                }
            },
        )

    indexed_count = 0
    for start in range(0, len(passages), BATCH_SIZE):
        batch = passages[start : start + BATCH_SIZE]
        vectors = embed([passage["text"] for passage in batch])
        actions = [
            {
                "_index": INDEX,
                "_id": passage["docid"],
                "_source": {
                    "title": passage["title"],
                    "text": passage["text"],
                    "embedding": vector,
                },
            }
            for passage, vector in zip(batch, vectors, strict=True)
        ]
        indexed, _ = helpers.bulk(client, actions)
        indexed_count += indexed
        if indexed_count % 50 == 0:
            print(f"색인 진행: {indexed_count}/{len(passages)}개 청크", flush=True)

    client.indices.refresh(index=INDEX)
    print(f"색인 완료: {indexed_count}개 청크")


if __name__ == "__main__":
    with Elasticsearch(
        "https://localhost:9200",
        basic_auth=("elastic", os.environ["ES_PASSWORD"]),
        verify_certs=False,
        ssl_show_warn=False,
    ) as client:
        index_passages(client)
