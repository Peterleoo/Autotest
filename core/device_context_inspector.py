import re
import logging
import subprocess
from typing import Dict, Any, Optional

logger = logging.getLogger("DeviceContextInspector")

class DeviceContextInspector:
    """
    端侧情境实时探针 (Device Context Inspector)
    在 AI 规划与决策前毫秒级探测物理真机当前状态：
    1. 应用宿主状态：是否安装、当前前台是谁 (Package / Activity)；
    2. 视觉语义定性：当前停留在什么页面 (桌面/首页/列表页/详情页/登录拦截)；
    3. 输出面向大模型的“前置事实与差量规划约束”。
    """

    @classmethod
    def inspect(cls, adb_bin: str, device_id: str, target_package: Optional[str] = None) -> Dict[str, Any]:
        target_package = target_package or ""
        result = {
            "device_id": device_id,
            "target_package": target_package,
            "is_installed": False,
            "is_foreground": False,
            "current_package": "",
            "current_activity": "",
            "scene_type": "UNKNOWN",
            "screen_keywords": [],
            "planning_hint": ""
        }

        if not device_id or device_id in ["mock-device", "local-simulator", "default"]:
            result["planning_hint"] = "仿真/本地测试环境，按标准基线规划流程"
            return result

        try:
            # 1. 检查是否安装
            res_pm = subprocess.run([adb_bin, "-s", device_id, "shell", "pm", "path", target_package], capture_output=True, text=True, timeout=3)
            result["is_installed"] = (res_pm.returncode == 0 and "package:" in res_pm.stdout)

            # 2. 检查当前前台窗口 (mCurrentFocus)
            res_focus = subprocess.run([adb_bin, "-s", device_id, "shell", "dumpsys", "window"], capture_output=True, text=True, timeout=3)
            focus_line = ""
            for line in res_focus.stdout.splitlines():
                if "mCurrentFocus" in line:
                    focus_line = line
                    break

            if focus_line:
                # 样例: mCurrentFocus=Window{e387170 u0 com.miui.home/com.miui.home.launcher.Launcher}
                match = re.search(r'([a-zA-Z0-9_\.]+)/([a-zA-Z0-9_\.]+)', focus_line)
                if match:
                    result["current_package"] = match.group(1)
                    result["current_activity"] = match.group(2)
                    if not target_package and "launcher" not in result["current_package"].lower():
                        target_package = result["current_package"]
                        result["target_package"] = target_package
                        result["is_installed"] = True
                    result["is_foreground"] = bool(target_package and result["current_package"] == target_package)

            # 3. 超轻量截屏感知与语义定性 (优先使用显存 RAW 直读 + PC 端硬件加速)
            screen_bytes = None
            try:
                from core.screen_stream_hub import _capture_raw_and_encode_sync
                f_data = _capture_raw_and_encode_sync(adb_bin, device_id)
                if f_data and f_data.get("jpeg"):
                    screen_bytes = f_data["jpeg"]
            except Exception:
                pass

            if not screen_bytes:
                res_cap = subprocess.run([adb_bin, "-s", device_id, "exec-out", "screencap", "-p"], capture_output=True, timeout=3)
                if res_cap.returncode == 0 and res_cap.stdout:
                    screen_bytes = res_cap.stdout

            if screen_bytes:
                try:
                    from core.vision_ocr import VisionOCR
                    elements, _ = VisionOCR.recognize_elements(screen_bytes)
                    texts = [e.get("text", "") for e in elements if e.get("text")]
                    result["screen_keywords"] = texts[:15]
                    all_text_str = " ".join(texts)

                    # 语义定性匹配
                    if "launcher" in result["current_activity"].lower() or any(k in all_text_str for k in ["小米钱包", "便签", "相机", "相册"]):
                        result["scene_type"] = "DESKTOP"
                        result["planning_hint"] = "【桌面状态】：待测应用未在前台，需冷启动并打开待测应用。"
                    elif any(k in all_text_str for k in ["手机号登录", "本机号码一键登录", "注册/登录", "验证码登录"]):
                        result["scene_type"] = "APP_LOGIN_BARRIER"
                        result["planning_hint"] = "【登录拦截状态】：当前屏幕弹出了登录拦截授权浮层，需先勾选协议并完成快速登录自愈。"
                    elif any(k in all_text_str for k in ["参考首付", "带看记录", "经纪人", "户型分间", "房源核验码", "同小区二手房"]):
                        result["scene_type"] = "APP_DETAIL_PAGE"
                        result["planning_hint"] = "【房源详情页】：应用已在前台但停留在历史房源详情页，规划的第一步必须是【从当前详情页点击返回键退回列表/首页】，严禁重复冷启动打开App！"
                    elif any(k in all_text_str for k in ["历史搜索", "热门搜索", "大家都在搜", "清空搜索", "搜索发现"]) or ("取消" in all_text_str and any(k in all_text_str for k in ["搜索", "找房", "请输入", "楼盘"])):
                        result["scene_type"] = "APP_SEARCH_PAGE"
                        result["planning_hint"] = "【搜索页面】：待测应用已在前台但停留在搜索子页面，未处于首页主界面。规划的第一步必须是【点击取消或返回键退回首页】，然后再从主界面导航至目标业务！"
                    elif any(k in all_text_str for k in ["区域", "总价", "户型", "排序", "筛选", "岳麓区", "雨花区"]) and "二手房" in all_text_str:
                        result["scene_type"] = "APP_LIST_PAGE"
                        result["planning_hint"] = "【房源列表页】：应用已在前台且已处于二手房列表页，无需重复进入二手房入口，可直接从当前列表执行筛选与排序！"
                    elif any(k in all_text_str for k in ["二手房", "新房", "租房", "委托服务", "小区找房"]):
                        result["scene_type"] = "APP_HOME_PAGE"
                        result["planning_hint"] = "【应用首页】：应用已在前台并处于主界面，无需重复冷启动，直接定位目标入口。"
                    else:
                        result["scene_type"] = "APP_RUNNING"
                        result["planning_hint"] = "应用已在前台运行，优先从当前页面顺势执行目标操作。"
                except Exception as ex:
                    logger.warning(f"OCR 语义定性异常: {ex}")

        except Exception as e:
            logger.warning(f"端侧情境探测失败: {e}")
            result["planning_hint"] = "探测真机状态超时，按标准流程规划"

        logger.info(f"📱 [端侧实时情境探针] 结果: is_fg={result['is_foreground']}, scene={result['scene_type']}, hint={result['planning_hint']}")
        return result
