import json
from pathlib import Path
from pprint import pprint

corpus = Path(__file__).resolve().parent / "dataset" / "corpus.jsonl"

with corpus.open(encoding="utf-8") as file:
    for line in file:
        row = json.loads(line)
        if row["docid"] == "64649#3":
            article_id, chunk_number = row["docid"].rsplit("#", 1)
            pprint({
                "title": row["title"],
                "article_id": article_id,
                "chunk_index": int(chunk_number),
                "text": row["text"],
            }, sort_dicts=False)
            break
