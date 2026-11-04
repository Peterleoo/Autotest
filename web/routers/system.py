# -*- coding: utf-8 -*-
"""配置、模型、授权与环境自检接口"""
from fastapi import APIRouter
import os
import json
import shutil
import subprocess
from typing import Optional
from fastapi import Form
from config.settings import settings
from config.ai_config import ai_config
from core.auth_manager import AuthManager

from web.shared import (
    BASE_DIR,
    app_mgr,
)

router = APIRouter()


auth_mgr = AuthManager()


@router.get("/api/system/preflight")
async def system_preflight():
    """对话流前置链路全景巡检：检测 AI 接入状态、待测应用包、在线物理真机"""
    provider = (ai_config.PROVIDER or "deepseek").lower()
    ai_ready = False
    ai_msg = ""
    
    if provider == "hermes":
        ai_ready = bool(ai_config.HERMES_API_KEY)
        ai_msg = "Hermes 网关已连接" if ai_ready else "Hermes 未配置 API Key"
    elif provider == "antigravity":
        try:
            from core.antigravity_oauth import AntigravityOAuth
            ai_ready = AntigravityOAuth().is_logged_in() or bool(ai_config.ANTIGRAVITY_API_KEY)
        except Exception:
            ai_ready = bool(ai_config.ANTIGRAVITY_API_KEY)
        ai_msg = "Google Antigravity 已就绪" if ai_ready else "Antigravity 未登录或未配置 API Key"
    elif provider == "deepseek":
        ai_ready = bool(ai_config.DEEPSEEK_API_KEY)
        ai_msg = "DeepSeek 驱动已就绪" if ai_ready else "DeepSeek 未配置 API Key"
    elif provider in ["openai", "claude"]:
        key = ai_config.OPENAI_API_KEY if provider == "openai" else ai_config.ANTHROPIC_API_KEY
        ai_ready = bool(key)
        ai_msg = f"{provider.upper()} 已就绪" if ai_ready else f"{provider.upper()} 未配置 API Key"
    else:
        ai_ready = bool(ai_config.DEEPSEEK_API_KEY or ai_config.ANTIGRAVITY_API_KEY)
        ai_msg = "AI 模型已接入" if ai_ready else "未检测到有效 AI 提供商配置"

    model_info = ai_config.get_current_model_info()

    # 2. 检查待测应用包
    apks = list(settings.APPS_DIR.glob("*.apk"))
    app_ready = len(apks) > 0
    current_app_name = apks[0].name if app_ready else ""
    app_msg = f"已就绪: {current_app_name}" if app_ready else "未检测到待测应用包 (apps/ 目录为空)"

    # 3. 检查物理真机
    devices = app_mgr.get_connected_devices()
    device_ready = len(devices) > 0
    device_msg = f"已连接 {len(devices)} 台真机" if device_ready else "未检测到物理真机设备 (请开启 USB 调试)"

    missing = []
    if not ai_ready:
        missing.append("ai")
    if not app_ready:
        missing.append("app")
    if not device_ready:
        missing.append("device")

    return {
        "success": True,
        "ready": len(missing) == 0,
        "missing": missing,
        "checks": {
            "ai": {
                "ready": ai_ready,
                "provider": provider,
                "model": model_info.get("model", ""),
                "display_name": model_info.get("name", provider),
                "message": ai_msg
            },
            "app": {
                "ready": app_ready,
                "count": len(apks),
                "current_app": current_app_name,
                "message": app_msg
            },
            "device": {
                "ready": device_ready,
                "count": len(devices),
                "devices": devices,
                "message": device_msg
            }
        }
    }


@router.get("/api/config")
async def get_config():
    """获取当前 AI 模型配置与状态"""
    from core.antigravity_oauth import AntigravityOAuth
    oauth = AntigravityOAuth()
    ag_state = oauth.get_state()
    model_info = ai_config.get_current_model_info()

    return {
        "provider": ai_config.PROVIDER,
        "current_model": model_info["model"],
        "display_name": model_info["name"],
        "hermes": {
            "ready": True,
            "model": ai_config.HERMES_MODEL,
            "available_models": ["deepseek-flash", "deepseek-chat", "deepseek-coder"]
        },
        "antigravity": {
            "ready": ag_state["is_logged_in"],
            "email": ag_state["email"],
            "model": ag_state["current_model"],
            "available_models": ag_state["models"]
        },
        "deepseek": {
            "ready": bool(ai_config.DEEPSEEK_API_KEY),
            "model": ai_config.DEEPSEEK_MODEL,
            "available_models": ["deepseek-chat", "deepseek-reasoner"]
        },
        "openai": {
            "ready": bool(ai_config.OPENAI_API_KEY),
            "model": ai_config.OPENAI_MODEL,
            "available_models": ["gpt-4o", "gpt-4o-mini", "o3-mini", "custom"]
        }
    }


@router.post("/api/config")
async def update_config(
    provider: str = Form(...),
    model: Optional[str] = Form(None),
    app_filename: Optional[str] = Form(None),
    app_package: Optional[str] = Form(None),
    app_label: Optional[str] = Form(None),
    app_activity: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None),
    base_url: Optional[str] = Form(None)
):
    """在 Web 端动态保存模型配置与切换激活模型"""
    env_path = BASE_DIR / ".env"
    
    keys_to_set = {
        "AI_PROVIDER": provider,
    }

    if provider == "hermes":
        if model: keys_to_set["HERMES_MODEL"] = model
        if api_key: keys_to_set["HERMES_API_KEY"] = api_key
        if base_url: keys_to_set["HERMES_BASE_URL"] = base_url
    elif provider == "antigravity":
        if model:
            keys_to_set["ANTIGRAVITY_MODEL"] = model
            from core.antigravity_oauth import AntigravityOAuth
            AntigravityOAuth().set_current_model(model)
    elif provider == "deepseek":
        if model: keys_to_set["DEEPSEEK_MODEL"] = model
        if api_key: keys_to_set["DEEPSEEK_API_KEY"] = api_key
        if base_url: keys_to_set["DEEPSEEK_BASE_URL"] = base_url
    else:
        if model: keys_to_set["OPENAI_MODEL"] = model
        if api_key: keys_to_set["OPENAI_API_KEY"] = api_key
        if base_url: keys_to_set["OPENAI_BASE_URL"] = base_url

    # 同步更新运行态环境变量与 .env 文件
    for k, v in keys_to_set.items():
        if v:
            os.environ[k] = str(v)

    # 核心：实时同步内存中全局 ai_config 单例
    ai_config.PROVIDER = provider

    if env_path.exists():
        existing_env = env_path.read_text(encoding="utf-8")
    else:
        existing_env = ""

    env_lines = [l for l in existing_env.split("\n") if l.strip() and not any(l.startswith(k + "=") for k in keys_to_set.keys())]
    for k, v in keys_to_set.items():
        if v:
            env_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(env_lines), encoding="utf-8")
    
    current_m = keys_to_set.get(f"{provider.upper()}_MODEL") or model or "default"
    return {"success": True, "message": f"成功切换为 [{provider.upper()}] 模型: {current_m}"}


@router.post("/api/config/fetch_models")
def fetch_remote_models(
    provider: str = Form(...),
    api_key: Optional[str] = Form(None),
    base_url: Optional[str] = Form(None)
):
    """在线动态向服务商拉取可用模型列表"""
    if provider == "antigravity":
        from core.antigravity_oauth import AntigravityOAuth
        oauth = AntigravityOAuth()
        state = oauth.get_state()
        models = state.get("models", ["gemini-3.8-flash-high", "gemini-2.5-flash", "gemini-2.5-pro"])
        return {"success": True, "models": models, "message": f"成功获取 Google 官方 {len(models)} 个可用多模态模型"}
    
    effective_url = base_url
    if not effective_url:
        if provider == "deepseek":
            effective_url = "https://api.deepseek.com"
        elif provider == "hermes":
            effective_url = os.environ.get("HERMES_BASE_URL", "http://10.10.20.108:8080/v1")
        else:
            effective_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
            
    effective_key = api_key or os.environ.get(f"{provider.upper()}_API_KEY", "")
    
    url = (effective_url or "").rstrip("/")
    if not url.endswith("/models"):
        if "/v1" in url:
            models_endpoint = f"{url}/models"
        else:
            models_endpoint = f"{url}/v1/models"
    else:
        models_endpoint = url

    try:
        import urllib.request, json
        req = urllib.request.Request(models_endpoint)
        if effective_key:
            req.add_header("Authorization", f"Bearer {effective_key}")
        req.add_header("User-Agent", "AutotestAI-Client/2.0")
        
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            data_list = res_data.get("data", [])
            model_ids = []
            for item in data_list:
                if isinstance(item, dict) and "id" in item:
                    model_ids.append(item["id"])
                elif isinstance(item, str):
                    model_ids.append(item)
            
            if model_ids:
                return {
                    "success": True,
                    "models": model_ids,
                    "message": f"成功在线探测并拉取到 {len(model_ids)} 个可用模型"
                }
    except Exception as e:
        pass
        
    fallback = []
    if provider == "deepseek":
        fallback = ["deepseek-chat", "deepseek-reasoner"]
    elif provider == "hermes":
        fallback = ["deepseek-flash", "deepseek-chat", "deepseek-coder"]
    else:
        fallback = ["gpt-4o", "gpt-4o-mini", "custom"]
        
    return {
        "success": False,
        "models": fallback,
        "message": "服务商接口未能即时响应，已加载常用模型列表"
    }


@router.get("/api/settings/env_status")
def get_env_status():
    """获取本地 ADB 与运行环境状态"""
    import subprocess, shutil
    adb_path = shutil.which("adb")
    adb_version = "未检测到 ADB 命令 (请确认已加入环境变量 PATH)"
    adb_ready = False
    
    if adb_path:
        try:
            res = subprocess.run([adb_path, "version"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                adb_ready = True
                first_line = res.stdout.strip().split("\n")[0]
                adb_version = first_line
        except Exception:
            pass
            
    return {
        "adb": {
            "ready": adb_ready,
            "version": adb_version,
            "path": adb_path or "adb"
        },
        "paths": {
            "env_file": str(BASE_DIR / ".env"),
            "solidified_cases": str(BASE_DIR / "solidified_cases"),
            "reports": str(BASE_DIR / "reports")
        }
    }


@router.get("/api/antigravity/status")
async def get_antigravity_status():
    """获取 Google Antigravity OAuth 授权状态"""
    from core.antigravity_oauth import AntigravityOAuth
    oauth = AntigravityOAuth()
    return oauth.get_state()


@router.post("/api/antigravity/login")
async def start_antigravity_login():
    """发起 Google OAuth 重新登录"""
    from core.antigravity_oauth import AntigravityOAuth
    oauth = AntigravityOAuth()
    url = oauth.start_login()
    return {"success": True, "auth_url": url, "message": "已在系统默认浏览器中打开 Google 登录授权页，请完成授权。"}


@router.post("/api/antigravity/switch_model")
async def switch_antigravity_model(model: str = Form(...)):
    """切换 Google Antigravity 的具体模型"""
    from core.antigravity_oauth import AntigravityOAuth
    oauth = AntigravityOAuth()
    oauth.set_current_model(model)
    os.environ["ANTIGRAVITY_MODEL"] = model
    return {"success": True, "model": model, "message": f"Google Antigravity 模型已切换为: {model}"}


# ==================== 邀请码云端校验与授权许可管理 (PM Harness 机制) ====================

@router.get("/api/auth/status")
async def get_auth_status():
    """获取系统当前邀请码授权状态与许可信息"""
    return auth_mgr.get_status()


@router.post("/api/auth/verify_invite")
async def verify_invite(code: str = Form(...)):
    """提交邀请码进行云端在线鉴权与本地激活"""
    return auth_mgr.verify_invite_code(code)
