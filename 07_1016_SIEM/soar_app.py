# /// script
# requires-python = ">=3.12"
# dependencies = ["fastapi>=0.115,<1", "pydantic>=2,<3", "uvicorn>=0.30,<1", "httpx>=0.27,<1"]
# ///
"""대응 앱: SIEM 경보를 받아 인증 앱의 계정 차단 API를 호출합니다."""

import argparse
import json
import logging
import sys
from typing import Literal

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


app = FastAPI(title="SOAR 역할 실습 — 대응 앱")
app.state.login_url = None
logger = logging.getLogger("uvicorn.error")


class SiemAlert(BaseModel):
    """JSON body shared by the connector test and per-alert rule action."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    alert_id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    rule_name: str = Field(min_length=1)
    severity: Literal["low", "medium", "high", "critical"]
    # Connector tests use "manual-test"; rule actions supply {{date}}.
    action_time: str = Field(min_length=1)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/siem")
def receive_siem_alert(payload: SiemAlert, request: Request):
    logger.info(
        "SIEM webhook received:\n%s",
        json.dumps(payload.model_dump(), ensure_ascii=False, indent=2),
    )
    result = {"received": True, "alert_id": payload.alert_id}
    if request.app.state.login_url and payload.severity in {"high", "critical"}:
        try:
            response = httpx.post(
                f"{request.app.state.login_url.rstrip('/')}/block",
                timeout=3, trust_env=False,
            )
            response.raise_for_status()
            result["action"] = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "로그인 앱의 차단 API 호출에 실패했습니다.") from exc
    return result


if __name__ == "__main__":
    # Keep Korean payloads readable when Windows redirects console output.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="SIEM 경보를 수신하고 인증 앱에 계정 차단을 요청합니다.")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--login-url", help="계정 차단 API를 제공하는 인증 앱 주소")
    args = parser.parse_args()
    app.state.login_url = args.login_url
    uvicorn.run(app, host="127.0.0.1", port=args.port)
