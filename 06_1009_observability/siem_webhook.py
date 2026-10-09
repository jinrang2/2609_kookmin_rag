# /// script
# requires-python = ">=3.12"
# dependencies = ["fastapi>=0.115,<1", "uvicorn>=0.30,<1"]
# ///
"""Local SIEM webhook receiver: uv run --script siem_webhook.py.

uv installs this script's dependencies in an isolated environment.
Received payloads are printed to the terminal; no RAG analysis runs here.
"""

import argparse
import json
import logging
import sys
from typing import Any

import uvicorn
from fastapi import FastAPI


app = FastAPI(title="SIEM Webhook 실습")
logger = logging.getLogger("uvicorn.error")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook/siem")
def receive_siem_alert(payload: dict[str, Any]):
    logger.info(
        "SIEM webhook received:\n%s",
        json.dumps(payload, ensure_ascii=False, indent=2),
    )
    return {"received": True, "alert_id": payload.get("alert_id")}


if __name__ == "__main__":
    # Keep Korean payloads readable when Windows redirects console output.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="SIEM 경보 JSON을 수신하고 터미널에 출력합니다.")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port)
