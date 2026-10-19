#!/usr/bin/env python3
"""
tools/antigravity_bridge.py - 独立的轻量级 Google Antigravity 本地 OpenAI 协议桥接服务
监听 127.0.0.1:19387，将标准 OpenAI chat.completions 请求通过 Google OAuth 凭据与本地代理转发至 Google Antigravity Code Assist 上游。
"""

import os
import sys
import json
import uuid
import time
import base64
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [AntigravityBridge] %(message)s")
logger = logging.getLogger("AntigravityBridge")

app = FastAPI(title="Google Antigravity OpenAI Bridge", version="1.0.0")

CONFIG_PATHS = [
    Path(__file__).resolve().parent.parent / "config" / "antigravity_oauth.json",
    Path(r"F:\PM-product\data\desktop-home\gemini-oauth-bridge.json")
]

PROXIES = {
    "http": os.getenv("ANTIGRAVITY_PROXY", "http://127.0.0.1:7897"),
    "https": os.getenv("ANTIGRAVITY_PROXY", "http://127.0.0.1:7897")
}

CLIENT_ID = base64.b64decode("MTA3MTAwNjA2MDU5MS10bWhzc2luMmgyMWxjcmUyMzV2dG9sb2poNGc0MDNlcC5hcHBzLmdvb2dsZXVzZXJjb250ZW50LmNvbQ==").decode()
CLIENT_SECRET = base64.b64decode("R09DU1BYLUs1OEZXUjQ4NkxkTEoxbUxCOHNYQzR6NnFEQWY=").decode()

class TokenManager:
    _cached_token: Optional[str] = None
    _expires_at: float = 0

    @classmethod
    def get_token_and_project(cls) -> tuple[Optional[str], str]:
        cfg_data = None
        for p in CONFIG_PATHS:
            if p.exists():
                try:
                    cfg_data = json.loads(p.read_text(encoding="utf-8"))
                    break
                except Exception:
                    pass

        if not cfg_data:
            return None, "aicode-consumers"

        tokens = cfg_data.get("tokens", {})
        refresh_token = tokens.get("refresh_token")
        access_token = tokens.get("access_token")
        project = cfg_data.get("project", "aicode-consumers")

        # 缓存有效直接返回
        if cls._cached_token and time.time() < cls._expires_at - 60:
            return cls._cached_token, project

        if not refresh_token:
            return access_token, project

        # 通过代理向 Google 刷新 Token
        try:
            resp = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                },
                proxies=PROXIES,
                timeout=12
            )
            if resp.status_code == 200:
                data = resp.json()
                cls._cached_token = data.get("access_token")
                cls._expires_at = time.time() + data.get("expires_in", 3600)
                logger.info("✅ 成功刷新 Google Antigravity Access Token")
                return cls._cached_token, project
        except Exception as e:
            logger.warning(f"刷新 Access Token 遇到网络波动: {e}")

        return access_token or cls._cached_token, project

@app.get("/health")
@app.get("/gemini-oauth-bridge/health")
async def health():
    return {"status": "ok", "service": "antigravity_bridge", "port": 19387}

@app.get("/v1/models")
@app.get("/gemini-oauth-bridge/v1/models")
async def list_models():
    models = [
        "gemini-3.8-flash-high",
        "gemini-3.8-flash-medium",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-3-flash",
        "claude-sonnet-4-6"
    ]
    data = [{"id": m, "object": "model", "created": int(time.time()), "owned_by": "google"} for m in models]
    return {"object": "list", "data": data}

@app.post("/v1/chat/completions")
@app.post("/gemini-oauth-bridge/v1/chat/completions")
async def chat_completions(req: Request):
    body = await req.json()
    model = body.get("model", "gemini-3.8-flash-medium")
    messages = body.get("messages", [])

    token, project = TokenManager.get_token_and_project()
    if not token:
        return JSONResponse(
            status_code=401,
            content={"error": {"message": "Google Antigravity 凭证未配置或刷新失败", "type": "auth_error"}}
        )

    # 抽取用户输入与系统指令
    sys_instruction = ""
    prompt_text = ""
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            sys_instruction += f"{content}\n"
        elif role == "user":
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        prompt_text += f"{item.get('text', '')}\n"
            else:
                prompt_text += f"{content}\n"

    full_prompt = f"{sys_instruction}\n{prompt_text}".strip()

    upstream_url = "https://cloudcode-pa.googleapis.com/v1internal:generateContent"
    envelope = {
        "model": model,
        "project": project,
        "requestType": "agent",
        "requestId": f"agent-{uuid.uuid4()}",
        "userAgent": "antigravity",
        "request": {
            "contents": [
                {"role": "user", "parts": [{"text": full_prompt}]}
            ]
        }
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "antigravity/hub/2.24.0 darwin/arm64"
    }

    try:
        upstream_resp = requests.post(upstream_url, headers=headers, json=envelope, proxies=PROXIES, timeout=30)
        if upstream_resp.status_code == 200:
            res_json = upstream_resp.json()
            # 解析 candidates 得到 text
            out_text = ""
            candidates = res_json.get("response", {}).get("candidates", []) or res_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                out_text = "".join(p.get("text", "") for p in parts)
            
            return {
                "id": f"chatcmpl-{uuid.uuid4()}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": out_text},
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            }
        else:
            logger.warning(f"Google 上游返回非 200: {upstream_resp.status_code} - {upstream_resp.text[:200]}")
            return JSONResponse(
                status_code=upstream_resp.status_code,
                content={"error": {"message": f"Google 上游响应异常: {upstream_resp.status_code}", "detail": upstream_resp.text[:300]}}
            )
    except Exception as e:
        logger.error(f"调用 Google Antigravity 上游异常: {e}")
        return JSONResponse(
            status_code=502,
            content={"error": {"message": f"Bridge 请求上游失败: {e}", "type": "upstream_error"}}
        )

def main():
    logger.info("正在启动 Google Antigravity 本地桥接服务 @ 127.0.0.1:19387")
    uvicorn.run(app, host="127.0.0.1", port=19387, log_level="warning")

if __name__ == "__main__":
    main()
