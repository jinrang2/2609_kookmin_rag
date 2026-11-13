import argparse
import json
import os
from itertools import islice
from pathlib import Path

from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer

ES_URL = "https://localhost:9200"
ES_USERNAME = "elastic"
ES_PASSWORD = "elastic"

parser = argparse.ArgumentParser()
parser.add_argument("--limit", type=int, help="색인할 최대 문단 수")
parser.add_argument("--offset", type=int, default=0, help="앞에서 건너뛸 문단 수")
args = parser.parse_args()
if args.offset < 0 or (args.limit is not None and args.limit < 1):
    parser.error("--offset은 0 이상, --limit은 1 이상이어야 합니다.")

index = os.getenv("RAG_ES_INDEX", "rag-miracl-ko-e5-small")
default_corpus = Path(__file__).resolve().parent / "dataset" / "corpus.jsonl"
corpus = Path(os.getenv("RAG_CORPUS_PATH", str(default_corpus)))
facets_by_title = json.loads(corpus.with_name("facets-by-title.json").read_text(encoding="utf-8"))
with corpus.open(encoding="utf-8") as stream:
    end = None if args.limit is None else args.offset + args.limit
    passages = [json.loads(line) for line in islice((line for line in stream if line.strip()), args.offset, end)]
if not passages:
    parser.error("지정한 범위에 색인할 문단이 없습니다.")

model_name = "intfloat/multilingual-e5-small"
model = SentenceTransformer(model_name)
vectors = model.encode(
    [f"passage: {item['text']}" for item in passages],
    batch_size=16,
    normalize_embeddings=True,
    show_progress_bar=True,
)

with Elasticsearch(
    ES_URL,
    basic_auth=(ES_USERNAME, ES_PASSWORD),
    verify_certs=False,
    ssl_show_warn=False,
) as client:
    extra_fields = {
        "chunk_index": {"type": "integer"},
        "topic": {"type": "keyword"},
        "article_type": {"type": "keyword"},
    }
    if not client.indices.exists(index=index):
        client.indices.create(
            index=index,
            mappings={
                "_meta": {"embedding_model": model_name},
                "properties": {
                    "docid": {"type": "keyword"},
                    "title": {"type": "text"},
                    "text": {"type": "text"},
                    "source": {"type": "keyword"},
                    **extra_fields,
                    "embedding": {
                        "type": "dense_vector",
                        "dims": 384,
                        "similarity": "cosine",
                    },
                },
            },
        )
    else:
        client.indices.put_mapping(index=index, properties=extra_fields)

    actions = (
        {
            "_index": index,
            "_id": item["docid"],
            "_source": {
                **item,
                "chunk_index": int(item["docid"].rsplit("#", 1)[1]),
                "source": "MIRACL Korean / Wikipedia",
                **facets_by_title[item["title"]],
                "embedding": vector.tolist(),
            },
        }
        for item, vector in zip(passages, vectors, strict=True)
    )
    indexed, _ = helpers.bulk(client, actions, refresh="wait_for")
    print(f"색인 처리 {indexed}건 · 인덱스 {index}")
    print(f"확인용 첫 문단 ID: {passages[0]['docid']}")
