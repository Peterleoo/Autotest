# -*- coding: utf-8 -*-
"""应用包管理、安装与 App 项目接口"""
from fastapi import APIRouter
import subprocess
from typing import Optional, Dict, Any
from fastapi import UploadFile, File, Form, Body
from fastapi.responses import JSONResponse
from web.path_safety import safe_path
from config.settings import settings

from web.shared import (
    logger,
    KNOWN_APP_META,
    app_mgr,
)

router = APIRouter()


@router.get("/api/apps")
async def get_apps():
    """获取已下载的安装包列表与元数据（附带测试凭证）"""
    from core.credential_manager import CredentialManager
    apks = []
    for f in settings.APPS_DIR.glob("*.apk"):
        info = app_mgr.get_apk_info(f)
        size_mb = round(f.stat().st_size / (1024 * 1024), 1)
        cred = CredentialManager.get_credential(f.stem) or CredentialManager.get_credential(info.get("package") or "")
        apks.append({
            "filename": f.name,
            "label": info.get("label") or f.stem,
            "package": info.get("package") or settings.ANDROID_APP_PACKAGE,
            "activity": info.get("activity") or settings.ANDROID_APP_ACTIVITY,
            "version": info.get("version") or "最新版",
            "size": f"{size_mb} MB",
            "path": str(f),
            "credential": cred
        })
    return {"apps": apks}


@router.post("/api/apps/credentials")
async def save_app_credentials(data: Dict[str, Any] = Body(...)):
    """保存应用的预置测试账号凭证"""
    from core.credential_manager import CredentialManager
    app_key = data.get("app_key") or data.get("filename") or data.get("package")
    account = data.get("account", "").strip()
    password = data.get("password", "").strip()
    res = CredentialManager.set_credential(app_key, account, password)
    return {"success": True, "credential": res}


@router.get("/api/apps/check_installed")
async def check_app_installed(package: str, device_id: Optional[str] = None):
    """检测指定包名的应用是否已安装在目标真机设备上"""
    if not package:
        return {"installed": False, "message": "包名不能为空"}
    installed = app_mgr.is_app_installed(package, device_id=device_id)
    return {"installed": installed, "package": package, "device_id": device_id}


@router.delete("/api/apps/{filename}")
async def delete_app_package(filename: str):
    """从应用库中移除指定 APK 安装包"""
    apk_path = safe_path(settings.APPS_DIR, filename)
    if apk_path.exists():
        try:
            apk_path.unlink()
            return {"success": True, "message": f"已成功移除应用包: {filename}"}
        except Exception as e:
            return JSONResponse(status_code=500, content={"success": False, "message": str(e)})
    return JSONResponse(status_code=404, content={"success": False, "message": "文件不存在"})


@router.post("/api/install")
def install_app_to_device(device_id: Optional[str] = Form(None), filename: str = Form(...)):
    """安装指定 APK 到设备，支持针对小米 MIUI / 国内厂商安全限制的自适应降级与通道兜底"""
    apk_path = safe_path(settings.APPS_DIR, filename)
    if not apk_path.exists():
        return JSONResponse(status_code=404, content={"message": "安装包不存在"})

    adb_bin = app_mgr.adb_bin
    target_dev = device_id if (device_id and device_id not in ["mock-device", "local-simulator", "default"]) else None
    base_cmd = [adb_bin]
    if target_dev:
        base_cmd.extend(["-s", target_dev])

    try:
        # Step 1: 尝试标准 install -r -g 安装
        cmd_with_g = base_cmd + ["install", "-r", "-g", str(apk_path)]
        res = subprocess.run(cmd_with_g, capture_output=True, text=True, timeout=120)
        if "Success" in res.stdout:
            return {"success": True, "message": f"成功安装 {filename} 到设备 {target_dev or '默认真机'}"}

        # Step 2: 若触发权限安全异常 (常见于小米 MIUI)，自适应降级为不带 -g 的纯覆盖安装
        err_msg = (res.stdout + " " + res.stderr).strip()
        if "INSTALL_GRANT_RUNTIME_PERMISSIONS" in err_msg or "SecurityException" in err_msg:
            cmd_no_g = base_cmd + ["install", "-r", str(apk_path)]
            res2 = subprocess.run(cmd_no_g, capture_output=True, text=True, timeout=120)
            if "Success" in res2.stdout:
                return {"success": True, "message": f"成功安装 {filename} 到设备 {target_dev or '默认真机'}"}
            err_msg = (res2.stdout + " " + res2.stderr).strip()

        # Step 3: 若触发 USER_RESTRICTED (小米手机开发者选项中未开启【USB 安装】)
        if "INSTALL_FAILED_USER_RESTRICTED" in err_msg or "user_restricted" in err_msg.lower():
            try:
                remote_dest = f"/sdcard/Download/{filename}"
                subprocess.run(base_cmd + ["push", str(apk_path), remote_dest], capture_output=True, timeout=30)
                subprocess.run(base_cmd + ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", f"file://{remote_dest}", "-t", "application/vnd.android.package-archive"], capture_output=True, timeout=10)
                return {
                    "success": False,
                    "need_user_action": True,
                    "reason": "MIUI_USER_RESTRICTED",
                    "message": "已自动将安装包推送到手机并唤起安装弹窗！\n请在手机屏幕上点击【继续/允许安装】；\n或在手机【开发者选项】开启【USB 安装】与【USB 调试(安全设置)】。"
                }
            except Exception as e_push:
                logger.debug("忽略异常 @ install_app_to_device", exc_info=True)

        return {"success": False, "message": f"安装失败: {err_msg}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/api/download_qr")
async def download_from_qr(url_or_code: str = Form(...)):
    """从蒲公英短链或直链自动下载应用"""
    code = url_or_code.strip().split("/")[-1]
    if not code:
        return {"success": False, "message": "无效的短链或下载码"}
    
    # 调用获取脚本
    try:
        from get_pgyer_direct import get_apk
        get_apk(code)
        return {"success": True, "message": f"已成功触发并完成下载: {code}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/api/upload_app")
async def upload_app_package(file: UploadFile = File(...)):
    """接收用户上传的 APK / IPA 安装包文件并存入 apps 目录"""
    dest_path = safe_path(settings.APPS_DIR, file.filename or "")
    try:
        content = await file.read()
        dest_path.write_bytes(content)
        info = app_mgr.get_apk_info(dest_path)
        return {
            "success": True,
            "message": f"应用 {file.filename} 上传成功！已完成元数据解析",
            "filename": file.filename,
            "label": info.get("label") or dest_path.stem,
            "package": info.get("package") or settings.ANDROID_APP_PACKAGE
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": f"上传失败: {str(e)}"})


@router.get("/api/app_projects")
async def get_app_projects():
    """获取所有跟随 App 建立的测试项目文件夹清单与用例统计"""
    projects = []
    seen_ids = set()

    # 1. 优先扫描真机常见已知 App 项目工程
    for app_id, meta in KNOWN_APP_META.items():
        proj_dir = settings.SOLIDIFIED_DIR / app_id
        if proj_dir.exists() or app_id in ["xianghe_zhaofang", "xianghe_workbench"]:
            proj_dir.mkdir(parents=True, exist_ok=True)
            seen_ids.add(app_id)
            py_files = list(proj_dir.glob("*.py"))
            projects.append({
                "id": app_id,
                "name": meta["name"],
                "package": meta["package"],
                "version": meta["version"],
                "filename": f"{app_id}.apk",
                "case_count": len(py_files),
                "folder": f"tests/solidified/{app_id}",
                "is_current": (app_id == "xianghe_zhaofang")
            })

    # 2. 扫描 apps/ 本地 APK 安装包
    apps_dir = settings.APPS_DIR
    if apps_dir.exists():
        for apk_file in sorted(apps_dir.glob("*.apk")):
            app_id = apk_file.stem
            if app_id in seen_ids:
                continue
            seen_ids.add(app_id)
            info = app_mgr.get_apk_info(apk_file)
            proj_dir = settings.SOLIDIFIED_DIR / app_id
            proj_dir.mkdir(parents=True, exist_ok=True)
            py_files = list(proj_dir.glob("*.py"))
            app_label = info.get("label") or app_id.replace("_", " ").title()
            pkg = info.get("package") or f"com.{app_id}"
            ver = info.get("version") or "v1.0.0"
            projects.append({
                "id": app_id,
                "name": app_label,
                "package": pkg,
                "version": ver,
                "filename": apk_file.name,
                "case_count": len(py_files),
                "folder": f"tests/solidified/{app_id}",
                "is_current": (len(projects) == 0)
            })

    # 3. 扫描 tests/solidified/ 下已有的其他独立工程目录
    if settings.SOLIDIFIED_DIR.exists():
        for sub in sorted(settings.SOLIDIFIED_DIR.iterdir()):
            if sub.is_dir() and not sub.name.startswith((".", "_")) and sub.name not in seen_ids and sub.name != "__pycache__":
                seen_ids.add(sub.name)
                py_files = list(sub.glob("*.py"))
                known = KNOWN_APP_META.get(sub.name, {})
                projects.append({
                    "id": sub.name,
                    "name": known.get("name") or sub.name.replace("_", " ").title(),
                    "package": known.get("package") or f"com.{sub.name}",
                    "version": known.get("version") or "v1.0.0",
                    "filename": f"{sub.name}.apk",
                    "case_count": len(py_files),
                    "folder": f"tests/solidified/{sub.name}",
                    "is_current": False
                })

    if not projects:
        default_dir = settings.SOLIDIFIED_DIR / "default_app"
        default_dir.mkdir(parents=True, exist_ok=True)
        projects.append({
            "id": "default_app",
            "name": "移动待测应用工程",
            "package": "com.autotest.default",
            "version": "v1.0.0",
            "filename": "default_app.apk",
            "case_count": len(list(default_dir.glob("*.py"))),
            "folder": "tests/solidified/default_app",
            "is_current": True
        })

    return {"projects": projects, "current_project_id": projects[0]["id"] if projects else "demo_app"}
