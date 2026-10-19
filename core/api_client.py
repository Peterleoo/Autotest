import requests
import logging
from typing import Dict, Any, Optional
from config.settings import settings

logger = logging.getLogger("APIClient")

class APIClient:
    """
    统一接口测试客户端：支持自动 Token 维护、响应记录、断言与固化导出
    """
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.API_BASE_URL).rstrip("/")
        self.session = requests.Session()
        self.history: list = [] # 记录接口调用历史，便于 AI 查看和固化

    def set_header(self, key: str, value: str):
        """设置全局默认 Header（如 Authorization）"""
        self.session.headers[key] = value

    def request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """统一发起请求"""
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}/{endpoint.lstrip('/')}"
        timeout = kwargs.pop("timeout", settings.API_TIMEOUT)
        
        logger.info(f"发起接口请求: {method.upper()} {url}")
        resp = self.session.request(method=method.upper(), url=url, timeout=timeout, **kwargs)
        
        # 记录调用细节用于 AI 决策和代码固化
        record = {
            "method": method.upper(),
            "url": url,
            "endpoint": endpoint,
            "status_code": resp.status_code,
            "params": kwargs.get("params"),
            "json": kwargs.get("json"),
            "data": kwargs.get("data"),
            "headers": dict(resp.request.headers),
            "response_text": resp.text[:1000] # 截断避免超长
        }
        self.history.append(record)
        logger.info(f"接口响应状态码: {resp.status_code}")
        return resp

    def get(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("POST", endpoint, **kwargs)

    def put(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("PUT", endpoint, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("DELETE", endpoint, **kwargs)
