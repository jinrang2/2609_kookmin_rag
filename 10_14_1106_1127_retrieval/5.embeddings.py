import os

import requests

base_url = "https://labiv-llm.z.cs.kookmin.ac.kr"
ID = os.environ["LABIV_API_ID"]
PASSWORD = os.environ["LABIV_API_PASSWORD"]

path = "/v1/embeddings"
payload = {
    "model": "bge-m3",
    "input": [
      "서울은 대한민국의 수도이다.",
      "The capital of France is Paris."
    ]
}

response = requests.post(
    f"{base_url}{path}", auth=(ID, PASSWORD), json=payload, timeout=60
)
response.raise_for_status()
print(response.json())
