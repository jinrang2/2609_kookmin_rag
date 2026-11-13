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

    index = "rag-nori-nouns-python"
    body = {
        "settings": {
            "analysis": {
                "tokenizer": {
                    "korean_tokenizer": {
                        "type": "nori_tokenizer",
                        "decompound_mode": "discard"
                    }
                },
                "filter": {
                    "noun_pos": {
                        "type": "nori_part_of_speech",
                        "stoptags": [
                            "E", "IC", "J", "MAG", "MAJ", "MM", "NP",
                            "SF", "SP", "SSC", "SSO", "SC", "SY", "SE",
                            "VA", "VCN", "VCP", "VV", "VX",
                            "XPN", "XR", "XSA", "XSV", "UNKNOWN", "UNA", "NA", "VSV",
                        ],
                    },
                },
                "analyzer": {
                    "korean_text": {
                        "type": "custom",
                        "tokenizer": "korean_tokenizer",
                        "filter": ["noun_pos", "lowercase"],
                    }
                },
            }
        },
        "mappings": {
            "properties": {
                "docid": {"type": "keyword"},
                "title": {"type": "text", "analyzer": "korean_text"},
                "text": {"type": "text", "analyzer": "korean_text"},
            }
        },
    }
    if not client.indices.exists(index=index):
        client.indices.create(index=index, body=body)
    pprint(client.indices.get_mapping(index=index).body, sort_dicts=False)