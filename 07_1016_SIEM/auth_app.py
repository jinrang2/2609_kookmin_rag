# /// script
# requires-python = ">=3.12"
# dependencies = ["fastapi>=0.115,<1", "uvicorn>=0.30,<1"]
# ///
"""인증 앱: 로그인과 계정 차단·복구 API를 제공합니다."""

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


app = FastAPI(title="인증·계정 조치 앱")
user = {"username": "admin", "password": "1234", "blocked": False}


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/login")
def login(payload: LoginRequest):
    if payload.username != user["username"] or payload.password != user["password"]:
        raise HTTPException(401, "계정 또는 비밀번호가 틀렸습니다.")
    if user["blocked"]:
        raise HTTPException(403, "계정이 차단되었습니다.")
    return {"message": "로그인 성공", "username": user["username"]}


@app.post("/block")
def block():
    user["blocked"] = True
    return {"username": user["username"], "blocked": True}


@app.post("/unblock")
def unblock():
    user["blocked"] = False
    return {"username": user["username"], "blocked": False}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8082)
