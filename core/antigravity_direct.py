import os
import json
import time
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import requests

logger = logging.getLogger("AntigravityDirect")

CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
CLIENT_SECRET = "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"

TOKEN_FILES = [
    Path(__file__).resolve().parent.parent / "config" / "antigravity_oauth.json",
    Path(r"F:\PM-product\data\desktop-home\gemini-oauth-bridge.json")
]

class AntigravityDirectClient:
    """
    Google Antigravity 官方订阅直连客户端（原生 Python 实现）
    核心价值：
    1. 彻底摆脱对外部 PM-product 桌面应用 (127.0.0.1:19387) 的端口依赖；
    2. 基于官方 OAuth 凭证自动静默续期 Access Token；
    3. 直连 Google Cloud Code Assist / Antigravity 官方端点，消耗 Google AI Pro 订阅额度；
    4. 原生支持 Gemini 3.8 / 3.7 / 2.5 多模态视觉（图片理解）与推理决策。
    """
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("ANTIGRAVITY_MODEL", "gemini-3.8-flash-medium")
        self.proxy = {
            "http": os.getenv("HTTP_PROXY", "http://127.0.0.1:7897"),
            "https": os.getenv("HTTPS_PROXY", "http://127.0.0.1:7897")
        }
        self.session = requests.Session()
        self.session.proxies.update(self.proxy)
        self.config_data = self._load_token_data()
        self.token = self.ensure_access_token()

    def _load_token_data(self) -> Dict[str, Any]:
        for p in TOKEN_FILES:
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if data.get("tokens", {}).get("refresh_token"):
                        return data
                except Exception as e:
                    logger.warning(f"读取 Token 文件失败 {p}: {e}")
        raise RuntimeError("未找到有效的 Google Antigravity 授权凭证，请先在设置弹窗中完成 Google 授权登录。")

    def ensure_access_token(self) -> str:
        """确保获得有效的 Access Token，若即将过期则自动静默刷新"""
        tokens = self.config_data.get("tokens", {})
        access_token = tokens.get("access_token", "")
        expires_at = tokens.get("expiresAt", 0)
        refresh_token = tokens.get("refresh_token", "")

        # 预留 60 秒缓冲区
        now_ms = int(time.time() * 1000)
        if access_token and (expires_at - now_ms) > 60000:
            return access_token

        if not refresh_token:
            if access_token:
                return access_token
            raise RuntimeError("缺失 refresh_token，无法续期 Google 授权")

        logger.info("正在自动刷新 Google Antigravity Access Token...")
        try:
            resp = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                },
                proxies=self.proxy,
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                self.config_data["tokens"]["access_token"] = access_token
                self.config_data["tokens"]["expiresAt"] = now_ms + (expires_in * 1000)

                # 回写持久化
                for p in TOKEN_FILES:
                    if p.exists():
                        try:
                            p.write_text(json.dumps(self.config_data, indent=2, ensure_ascii=False), encoding="utf-8")
                        except Exception:
                            pass
                logger.info("Google Antigravity Access Token 自动刷新成功！")
                return access_token
            else:
                logger.error(f"刷新 Token 失败: {resp.text}")
                return access_token
        except Exception as e:
            logger.error(f"请求 Google Token 异常: {e}")
            return access_token

    def generate_content(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: Optional[str] = None
    ) -> Dict[str, Any]:
        """直连 Google Antigravity 端点进行生成决策"""
        token = self.ensure_access_token()
        url = "https://daily-cloudcode-pa.googleapis.com/v1internal:generateContent"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "antigravity/hub/2.24.0 darwin/arm64"
        }

        # 构造 user parts
        user_parts = []
        if image_base64:
            user_parts.append({
                "inlineData": {
                    "mimeType": "image/png",
                    "data": image_base64
                }
            })
        user_parts.append({"text": user_prompt})

        contents = [{"role": "user", "parts": user_parts}]

        request_payload = {
            "contents": contents
        }
        if system_prompt:
            request_payload["systemInstruction"] = {
                "role": "system",
                "parts": [{"text": system_prompt}]
            }

        body = {
            "model": self.model_name,
            "project": self.config_data.get("project", "aicode-consumers"),
            "requestType": "agent",
            "requestId": f"agent-{uuid.uuid4()}",
            "userAgent": "antigravity",
            "request": request_payload
        }

        max_retries = 3
        last_err = None
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"正在通过 Google Antigravity 官方授权调用 [{self.model_name}] (第 {attempt+1}/{max_retries} 次重试)...")
                else:
                    logger.info(f"正在通过 Google Antigravity 官方授权调用 [{self.model_name}]...")

                resp = self.session.post(url, headers=headers, json=body, timeout=35)
                if resp.status_code == 200:
                    data = resp.json()
                    cands = data.get("response", {}).get("candidates", [])
                    if cands:
                        parts = cands[0].get("content", {}).get("parts", [])
                        raw_text = "".join([p.get("text", "") for p in parts if "text" in p])
                        logger.info("Google Antigravity 官方响应成功！")
                        return self._parse_json(raw_text)
                    raise RuntimeError(f"Google 响应未包含候选内容: {data}")
                elif resp.status_code == 401:
                    # 强制重新刷新 token 并重试一次
                    self.config_data["tokens"]["expiresAt"] = 0
                    token = self.ensure_access_token()
                    headers["Authorization"] = f"Bearer {token}"
                    resp2 = self.session.post(url, headers=headers, json=body, timeout=35)
                    if resp2.status_code == 200:
                        cands = resp2.json().get("response", {}).get("candidates", [])
                        parts = cands[0].get("content", {}).get("parts", [])
                        raw_text = "".join([p.get("text", "") for p in parts if "text" in p])
                        return self._parse_json(raw_text)
                    raise RuntimeError(f"Google 鉴权失败 ({resp2.status_code}): {resp2.text[:200]}")
                else:
                    raise RuntimeError(f"Google 端点返回错误码 ({resp.status_code}): {resp.text[:300]}")
            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    wait_sec = 1.0 * (attempt + 1)
                    logger.warning(f"Antigravity 官方直连网络抖动 ({e})，正在等待 {wait_sec}s 自动重试 ({attempt+1}/{max_retries})...")
                    time.sleep(wait_sec)
                    # 重建 Session 防止连接池脏状态
                    self.session = requests.Session()
                    self.session.proxies.update(self.proxy)
                else:
                    logger.error(f"Antigravity 官方直连多次重试后仍然异常: {e}")
                    raise e

    def _parse_json(self, raw_text: str) -> Dict[str, Any]:
        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            return json.loads(raw_text)
        except Exception:
            start = raw_text.find("{")
            end = raw_text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(raw_text[start:end])
            return {"thought": raw_text, "action": "wait", "reason": "解析响应"}
