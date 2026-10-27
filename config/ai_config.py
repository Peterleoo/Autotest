import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class AIConfig:
    """
    多模型统一配置：支持 Hermes 企业网关、Google Antigravity OAuth、官方 DeepSeek 与通用 OpenAI 协议
    所有参数动态感知环境变量变更，支持运行态热切换模型
    """
    @property
    def PROVIDER(self) -> str:
        return os.getenv("AI_PROVIDER", "hermes").lower()

    @PROVIDER.setter
    def PROVIDER(self, value: str):
        if value:
            os.environ["AI_PROVIDER"] = str(value).lower()

    # 1. Hermes 企业网关（DeepSeek 高速推理引擎）
    @property
    def HERMES_API_KEY(self) -> str:
        return os.getenv("HERMES_API_KEY", "")

    @property
    def HERMES_BASE_URL(self) -> str:
        return os.getenv("HERMES_BASE_URL", "https://labela.xhj.com/hermes")

    @property
    def HERMES_MODEL(self) -> str:
        return os.getenv("HERMES_MODEL", "deepseek-flash")

    # 2. Google Antigravity OAuth 配置
    @property
    def ANTIGRAVITY_CONFIG_PATH(self) -> str:
        return os.getenv("ANTIGRAVITY_CONFIG_PATH", r"F:\PM-product\data\desktop-home\gemini-oauth-bridge.json")

    @property
    def ANTIGRAVITY_MODEL(self) -> str:
        return os.getenv("ANTIGRAVITY_MODEL", "gemini-2.5-flash")

    @property
    def ANTIGRAVITY_PROXY(self) -> str:
        return os.getenv("ANTIGRAVITY_PROXY", "http://127.0.0.1:7897")

    @property
    def ANTIGRAVITY_BASE_URL(self) -> str:
        return os.getenv("ANTIGRAVITY_BASE_URL", "http://127.0.0.1:19387/v1")

    @property
    def ANTIGRAVITY_API_KEY(self) -> str:
        return os.getenv("ANTIGRAVITY_API_KEY", "antigravity-oauth-bridge")

    # 3. 官方 DeepSeek 配置 (https://api.deepseek.com)
    @property
    def DEEPSEEK_API_KEY(self) -> str:
        return os.getenv("DEEPSEEK_API_KEY", "")

    @property
    def DEEPSEEK_BASE_URL(self) -> str:
        return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    @property
    def DEEPSEEK_MODEL(self) -> str:
        return os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # 4. 通用 OpenAI 兼容协议
    @property
    def OPENAI_API_KEY(self) -> str:
        return os.getenv("OPENAI_API_KEY", "")

    @property
    def OPENAI_BASE_URL(self) -> str:
        return os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    @property
    def OPENAI_MODEL(self) -> str:
        return os.getenv("OPENAI_MODEL", "gpt-4o")

    # 超时与采样
    @property
    def TIMEOUT(self) -> int:
        return int(os.getenv("AI_TIMEOUT", "60"))

    @property
    def TEMPERATURE(self) -> float:
        return float(os.getenv("AI_TEMPERATURE", "0.1"))

    def get_current_model_info(self) -> dict:
        p = self.PROVIDER
        if p == "hermes":
            return {"provider": "hermes", "name": "Hermes 企业网关", "model": self.HERMES_MODEL}
        elif p == "antigravity":
            return {"provider": "antigravity", "name": "Google Antigravity 官方授权", "model": self.ANTIGRAVITY_MODEL}
        elif p == "deepseek":
            return {"provider": "deepseek", "name": "DeepSeek 官方 API", "model": self.DEEPSEEK_MODEL}
        else:
            return {"provider": "openai", "name": "OpenAI / 本地大模型", "model": self.OPENAI_MODEL}

ai_config = AIConfig()
