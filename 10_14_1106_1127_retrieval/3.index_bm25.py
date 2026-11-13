import json
from pathlib import Path
from pprint import pprint

from elasticsearch import Elasticsearch, helpers

index = "rag-miracl-ko-bm25"
corpus = Path(__file__).resolve().parent / "dataset" / "corpus.jsonl"

with Elasticsearch(
    "https://localhost:9200",
    basic_auth=("elastic", "elastic"),
    verify_certs=False,
    ssl_show_warn=False,
) as client:
    if not client.indices.exists(index=index):
        raise SystemExit(f"Create the index in Kibana first: {index}")

    with corpus.open(encoding="utf-8") as file:
        rows = (json.loads(line) for line in file)
        actions = (
            {
                "_index": index,
                "_id": row["docid"],
                "_source": {"title": row["title"], "text": row["text"]},
            }
            for row in rows
        )
        count, _ = helpers.bulk(client, actions, refresh="wait_for")

    pprint({"indexed": count})
