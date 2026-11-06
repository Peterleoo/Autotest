# -*- coding: utf-8 -*-
"""Antigravity OAuth 客户端凭据：只从本地环境变量 / .env 读取，绝不写入代码库

仓库为公开仓库，任何凭据（含 base64 编码）都不得出现在源码中。
在本地 .env（已被 .gitignore 忽略）中配置：
    ANTIGRAVITY_CLIENT_ID=...
    ANTIGRAVITY_CLIENT_SECRET=...
"""
import os
from pathlib import Path
from typing import Tuple

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

CLIENT_ID_ENV = "ANTIGRAVITY_CLIENT_ID"
CLIENT_SECRET_ENV = "ANTIGRAVITY_CLIENT_SECRET"
# Google 反代（Antigravity）账号使用总开关：默认关闭，显式设为 true 才允许读取/刷新个人 OAuth 令牌
ENABLED_ENV = "ANTIGRAVITY_ENABLED"
_TRUTHY = {"1", "true", "yes", "on"}


class AntigravityDisabled(RuntimeError):
    """Google 反代账号已停用（ANTIGRAVITY_ENABLED 未开启）"""


def is_antigravity_enabled() -> bool:
    return os.getenv(ENABLED_ENV, "false").strip().lower() in _TRUTHY


def ensure_antigravity_enabled() -> None:
    """所有会使用个人 Google 账号/令牌的入口都必须先调用此检查"""
    if not is_antigravity_enabled():
        raise AntigravityDisabled(
            f"Google 反代（Antigravity）账号已停用，暂不允许使用。如需恢复，在本地 .env 中设置 {ENABLED_ENV}=true"
        )


class AntigravityCredentialsMissing(RuntimeError):
    pass


def get_client_credentials() -> Tuple[str, str]:
    """返回 (client_id, client_secret)；缺失时给出明确的配置指引"""
    ensure_antigravity_enabled()
    client_id = os.getenv(CLIENT_ID_ENV, "").strip()
    client_secret = os.getenv(CLIENT_SECRET_ENV, "").strip()
    if not client_id or not client_secret:
        raise AntigravityCredentialsMissing(
            f"未配置 Antigravity OAuth 客户端凭据：请在本地 .env 中设置 {CLIENT_ID_ENV} 与 {CLIENT_SECRET_ENV}"
        )
    return client_id, client_secret
