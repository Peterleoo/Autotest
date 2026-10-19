import os
import json
import base64
import time
import threading
import urllib.parse
import webbrowser
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger("AntigravityOAuth")

CLIENT_ID_B64 = "MTA3MTAwNjA2MDU5MS10bWhzc2luMmgyMWxjcmUyMzV2dG9sb2poNGc0MDNlcC5hcHBzLmdvb2dsZXVzZXJjb250ZW50LmNvbQ=="
CLIENT_SECRET_B64 = "R09DU1BYLUs1OEZXUjQ4NkxkTEoxbUxCOHNYQzR6NnFEQWY="

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs"
]

CONFIG_PATHS = [
    Path(__file__).resolve().parent.parent / "config" / "antigravity_oauth.json",
    Path(r"F:\PM-product\data\desktop-home\gemini-oauth-bridge.json")
]

class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    oauth_instance = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/oauth-callback":
            params = urllib.parse.parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            if code and self.oauth_instance:
                success = self.oauth_instance.exchange_code(code)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                if success:
                    html = """
                    <html><head><meta charset='utf-8'><title>Google 授权成功</title></head>
                    <body style='font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;text-align:center;padding:50px;background:#1e1e2d;color:#fff;'>
                        <h2 style='color:#4caf50;'>🎉 Google Antigravity 官方授权成功！</h2>
                        <p style='color:#aaa;'>账号已成功绑定并自动生成刷新凭证。您可以关闭当前网页，返回移动端自动化测试控制台。</p>
                    </body></html>
                    """
                else:
                    html = """
                    <html><head><meta charset='utf-8'><title>授权失败</title></head>
                    <body style='font-family:sans-serif;text-align:center;padding:50px;background:#1e1e2d;color:#fff;'>
                        <h2 style='color:#f44336;'>❌ 换取 Token 失败</h2>
                        <p style='color:#aaa;'>请检查本地代理 127.0.0.1:7897 是否在线后重试。</p>
                    </body></html>
                    """
                self.wfile.write(html.encode("utf-8"))
            else:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # 静默 HTTP 访问日志

class AntigravityOAuth:
    def __init__(self):
        self.client_id = base64.b64decode(CLIENT_ID_B64).decode("utf-8")
        self.client_secret = base64.b64decode(CLIENT_SECRET_B64).decode("utf-8")
        self.redirect_port = 51121
        self.redirect_uri = f"http://localhost:{self.redirect_port}/oauth-callback"
        self.proxies = {
            "http": "http://127.0.0.1:7897",
            "https": "http://127.0.0.1:7897"
        }
        self.server_thread = None

    def get_state(self) -> Dict[str, Any]:
        """读取当前的 OAuth 授权状态与可用模型"""
        current_model = os.environ.get("ANTIGRAVITY_MODEL", "gemini-3.8-flash-high")
        for p in CONFIG_PATHS:
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    tokens = data.get("tokens", {})
                    models = data.get("models", [
                        "gemini-3.8-flash-high",
                        "gemini-3.7-flash-high",
                        "gemini-2.5-flash",
                        "gemini-2.5-pro",
                        "gemini-3-flash"
                    ])
                    # 若配置中保存了 current_model，优先使用
                    saved_model = data.get("current_model")
                    if saved_model:
                        current_model = saved_model
                    return {
                        "is_logged_in": bool(tokens.get("refresh_token")),
                        "email": data.get("email", "未绑定"),
                        "project": data.get("project", "aicode-consumers"),
                        "tier": data.get("tier", "g1-pro-tier"),
                        "current_model": current_model,
                        "models": models,
                        "expires_at": tokens.get("expiresAt")
                    }
                except Exception:
                    pass
        return {
            "is_logged_in": False,
            "email": "未登录",
            "current_model": current_model,
            "models": ["gemini-3.8-flash-high", "gemini-2.5-flash", "gemini-2.5-pro"]
        }

    def set_current_model(self, model_name: str) -> bool:
        """设置并持久化当前调用的模型"""
        os.environ["ANTIGRAVITY_MODEL"] = model_name
        local_cfg = CONFIG_PATHS[0]
        if local_cfg.exists():
            try:
                data = json.loads(local_cfg.read_text(encoding="utf-8"))
                data["current_model"] = model_name
                local_cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                return True
            except Exception as e:
                logger.error(f"持久化模型选择失败: {e}")
        return True

    def _start_callback_server(self):
        """在后台单次监听 51121 端口以接收 OAuth 重定向回调"""
        try:
            _OAuthCallbackHandler.oauth_instance = self
            server = HTTPServer(("localhost", self.redirect_port), _OAuthCallbackHandler)
            server.timeout = 120  # 2 分钟超时
            logger.info(f"本地 OAuth 回调监听已就绪: http://localhost:{self.redirect_port}/oauth-callback")
            server.handle_request()  # 处理单次请求后退出
            server.server_close()
        except Exception as e:
            logger.warning(f"启动回调服务异常 (可能端口已在监听): {e}")

    def start_login(self) -> str:
        """生成授权链接、启动本地监听并在浏览器中打开"""
        # 启动后台监听线程
        threading.Thread(target=self._start_callback_server, daemon=True).start()

        params = {
            "access_type": "offline",
            "client_id": self.client_id,
            "prompt": "consent",
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "state": os.urandom(16).hex()
        }
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
        logger.info(f"正在打开 Google 授权登录页面: {auth_url}")
        webbrowser.open(auth_url)
        return auth_url

    def exchange_code(self, code: str) -> bool:
        """接收 code 并换取 access_token 与 refresh_token"""
        try:
            resp = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri
                },
                proxies=self.proxies,
                timeout=15
            )
            if resp.status_code != 200:
                logger.error(f"交换 Token 失败: {resp.text}")
                return False

            tokens = resp.json()
            # 获取用户 email
            user_info = requests.get(
                "https://www.googleapis.com/oauth2/v2/userinfo?alt=json",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                proxies=self.proxies,
                timeout=10
            ).json()

            # 保存配置
            save_data = {
                "tokens": {
                    "access_token": tokens.get("access_token"),
                    "refresh_token": tokens.get("refresh_token"),
                    "expiresAt": int(time.time() * 1000) + (tokens.get("expires_in", 3600) * 1000)
                },
                "email": user_info.get("email", ""),
                "project": "aicode-consumers",
                "tier": "g1-pro-tier",
                "current_model": os.environ.get("ANTIGRAVITY_MODEL", "gemini-3.8-flash-high"),
                "models": [
                    "gemini-3.8-flash-high",
                    "gemini-3.7-flash-high",
                    "gemini-2.5-flash",
                    "gemini-2.5-pro",
                    "gemini-3-flash",
                    "claude-sonnet-4-6"
                ]
            }

            local_cfg = CONFIG_PATHS[0]
            local_cfg.parent.mkdir(parents=True, exist_ok=True)
            local_cfg.write_text(json.dumps(save_data, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info(f"Google Antigravity 登录成功并持久化: {save_data['email']}")
            return True
        except Exception as e:
            logger.error(f"OAuth 换码异常: {e}")
            return False
