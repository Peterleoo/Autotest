import json
import logging
import base64
from typing import Dict, Any, List, Optional
from config.ai_config import ai_config

logger = logging.getLogger("LLMClient")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class LLMClient:
    """
    统一多模型客户端：支持 Antigravity / DeepSeek / Claude / OpenAI 等
    """
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.provider = (provider or ai_config.PROVIDER).lower()
        self.override_model = model
        self._init_client()

    def _init_client(self):
        logger.info(f"正在初始化 AI 模型驱动: {self.provider} (指定模型: {self.override_model})")
        if self.provider == "hermes":
            try:
                from anthropic import Anthropic
                self.client = Anthropic(
                    api_key=ai_config.HERMES_API_KEY,
                    base_url=ai_config.HERMES_BASE_URL
                )
                self.model_name = self.override_model or ai_config.HERMES_MODEL
                logger.info(f"Hermes 网关初始化成功: {self.model_name} @ {ai_config.HERMES_BASE_URL}")
            except Exception as e:
                logger.error(f"初始化 Hermes 客户端失败: {e}")
                self.client = None

        elif self.provider == "claude" or self.provider == "anthropic":
            try:
                from anthropic import Anthropic
                self.client = Anthropic(
                    api_key=ai_config.ANTHROPIC_API_KEY,
                    base_url=ai_config.ANTHROPIC_BASE_URL
                )
                self.model_name = self.override_model or ai_config.ANTHROPIC_MODEL
            except Exception as e:
                logger.error(f"初始化 Claude 客户端失败: {e}")
                self.client = None

        elif self.provider == "deepseek":
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=ai_config.DEEPSEEK_API_KEY,
                    base_url=ai_config.DEEPSEEK_BASE_URL,
                    timeout=ai_config.TIMEOUT
                )
                self.model_name = self.override_model or ai_config.DEEPSEEK_MODEL
            except Exception as e:
                logger.error(f"初始化 DeepSeek 客户端失败: {e}")
                self.client = None

        elif self.provider == "antigravity" or self.provider == "gemini":
            try:
                # 兼容 Gemini/Antigravity OpenAI 协议中转或原生 SDK
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=ai_config.ANTIGRAVITY_API_KEY,
                    base_url=ai_config.ANTIGRAVITY_BASE_URL,
                    timeout=ai_config.TIMEOUT,
                    max_retries=1
                )
                self.model_name = self.override_model or ai_config.ANTIGRAVITY_MODEL
            except Exception as e:
                logger.error(f"初始化 Antigravity 客户端失败: {e}")
                self.client = None

        else: # 默认 fallback 为 openai 兼容协议
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=ai_config.OPENAI_API_KEY,
                    base_url=ai_config.OPENAI_BASE_URL,
                    timeout=ai_config.TIMEOUT,
                    max_retries=1
                )
                self.model_name = self.override_model or ai_config.OPENAI_MODEL
            except Exception as e:
                logger.error(f"初始化 OpenAI 客户端失败: {e}")
                self.client = None

        self.last_fallback_info: Optional[Dict[str, Any]] = None

    @staticmethod
    def _is_local_endpoint_online(base_url: str, timeout: float = 0.5) -> bool:
        """极速探测本地中转网关端口是否在线（避免 OpenAI SDK 默认多轮重试耗费 10 秒）"""
        import socket
        from urllib.parse import urlparse
        try:
            parsed = urlparse(base_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if host in ["127.0.0.1", "localhost", "0.0.0.0"]:
                with socket.create_connection((host, port), timeout=timeout):
                    return True
            return True
        except Exception:
            return False

    def chat_decision(self, system_prompt: str, user_prompt: str, image_base64: Optional[str] = None, memory_context: Optional[str] = None) -> Dict[str, Any]:
        """
        向大模型发送意图并获得 JSON 格式的测试动作决策
        """
        if not self.client:
            raise RuntimeError(f"模型客户端 [{self.provider}] 未就绪，请检查 API Key 与 Base URL 配置。")

        # 🚀 自动装配连续会话记忆与端侧事实上下文 (Conversation Memory Injection)
        if memory_context and memory_context.strip():
            user_prompt = f"{memory_context.strip()}\n\n{user_prompt}"

        from core.memory_manager import MemoryManager
        est_tokens = MemoryManager.estimate_tokens(system_prompt + "\n" + user_prompt)
        self.last_estimated_tokens = est_tokens

        # 若是 Google Antigravity 官方授权，直接使用 AntigravityDirectClient 原生直连端点！
        if self.provider in ["antigravity", "gemini"]:
            try:
                from core.antigravity_direct import AntigravityDirectClient
                direct_client = AntigravityDirectClient(model_name=self.model_name)
                res = direct_client.generate_content(system_prompt, user_prompt, image_base64)
                logger.info(f"✨ Google Antigravity [{self.model_name}] 原生官方授权调用成功！")
                return res
            except Exception as e:
                logger.warning(
                    f"Google Antigravity 官方直连异常 ({e})，"
                    f"自动平滑降级至 Hermes 企业网关保底保障测试..."
                )
                try:
                    fallback_client = LLMClient(provider="hermes")
                    res = fallback_client.chat_decision(system_prompt, user_prompt, image_base64)
                    self.last_fallback_info = {
                        "fallback": True,
                        "original_provider": self.provider,
                        "fallback_provider": "hermes",
                        "model": fallback_client.model_name,
                        "reason": f"Google 官方授权端点异常: {e}"
                    }
                    if isinstance(res, dict):
                        res["_fallback_info"] = self.last_fallback_info
                    return res
                except Exception as fb_err:
                    raise RuntimeError(f"Google 授权端点异常 ({e}) 且备用网关异常 ({fb_err})")

        # 1. Claude / Hermes (Anthropic 格式) 调用分支
        if self.provider in ["hermes", "claude", "anthropic"]:
            content = []
            if image_base64:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_base64
                    }
                })
            content.append({"type": "text", "text": user_prompt})

            create_kwargs = {
                "model": self.model_name,
                "system": system_prompt,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": 2048
            }
            try:
                response = self.client.messages.create(**create_kwargs)
            except Exception as e:
                logger.error(f"调用模型失败: {e}")
                raise e

            # 遍历 content 取出 text（过滤 thinking block）
            raw_text = ""
            for block in response.content:
                if getattr(block, "type", "") == "text":
                    raw_text += getattr(block, "text", "")
                elif isinstance(block, dict) and block.get("type") == "text":
                    raw_text += block.get("text", "")

            if not raw_text and response.content:
                raw_text = str(response.content[-1])

        # 2. OpenAI / DeepSeek / Antigravity 兼容协议分支
        else:
            messages = [{"role": "system", "content": system_prompt}]
            user_content = []
            if image_base64:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                })
            user_content.append({"type": "text", "text": user_prompt})
            messages.append({"role": "user", "content": user_content})

            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=ai_config.TEMPERATURE,
                    response_format={"type": "json_object"} if "deepseek" not in self.model_name else None
                )
                raw_text = response.choices[0].message.content
            except Exception as e:
                logger.warning(f"调用 [{self.provider}] 异常: {e}，自动尝试 fallback 到 Hermes 企业网关...")
                if self.provider != "hermes":
                    try:
                        fallback_client = LLMClient(provider="hermes")
                        res = fallback_client.chat_decision(system_prompt, user_prompt, image_base64)
                        self.last_fallback_info = {
                            "fallback": True,
                            "original_provider": self.provider,
                            "fallback_provider": "hermes",
                            "model": fallback_client.model_name,
                            "reason": str(e)
                        }
                        if isinstance(res, dict):
                            res["_fallback_info"] = self.last_fallback_info
                        return res
                    except Exception:
                        pass
                raise RuntimeError(f"调用模型 [{self.provider}] 异常: {e}")

        parsed_json = self._parse_json_response(raw_text)
        if self.last_fallback_info and isinstance(parsed_json, dict):
            parsed_json["_fallback_info"] = self.last_fallback_info
        return parsed_json

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        # 清理 markdown codeblock
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except Exception as e:
            logger.warning(f"直接解析 JSON 失败: {e}，尝试提取子串...")
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end+1])
                except Exception:
                    pass
            return {"status": "ok", "action": "step_inferred", "raw_content": text[:300]}
