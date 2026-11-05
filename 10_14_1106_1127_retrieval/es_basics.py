from pprint import pprint

from elasticsearch import Elasticsearch

ES_URL = "https://localhost:9200"
ES_USERNAME = "elastic"
ES_PASSWORD = "elastic"

index = "kibana_sample_data_ecommerce"

with Elasticsearch(
    ES_URL,
    basic_auth=(ES_USERNAME, ES_PASSWORD),
    verify_certs=False,
    ssl_show_warn=False,
) as client:
    
    body = {
        "size": 3,
        "_source": ["order_id", "category"],
        "query": {
            "match": {"category": "Clothing"}
        },
    }

    response = client.search(index=index, body=body)

    hits = response["hits"]["hits"]

    for hit in hits:
        pprint(hit)

    if hits:
        doc = client.get(index=index, id=hit['_id'], source_includes=["order_id", "category"])
        print(f"조회대상 _id:{hit['_id']}")
        pprint(doc.body["_source"])
