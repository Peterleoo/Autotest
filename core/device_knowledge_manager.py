import os
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("DeviceKnowledgeManager")

BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_FILE = BASE_DIR / "data" / "device_knowledge.json"

class DeviceKnowledgeManager:
    """
    移动端设备画像识别与故障自进化知识库管理器：
    1. 毫秒级识别物理真机型号、品牌、系统版本与定制 ROM；
    2. 本地知识库秒级匹配：有记录直接出排查指引（0 秒 0 Token）；
    3. 未知异常 AI 自学习：自动调用大模型推演根因与解法，并持久化存盘进化。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DeviceKnowledgeManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        from core.app_manager import AppManager
        self.adb_bin = AppManager().adb_bin
        self.knowledge_path = KNOWLEDGE_FILE
        self._cache = self._load_knowledge()

    def _load_knowledge(self) -> Dict[str, Any]:
        """读取本地设备知识库文件"""
        if not self.knowledge_path.exists():
            return {"version": "1.0.0", "devices": {}, "brand_rules": {}}
        try:
            with open(self.knowledge_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载设备知识库文件失败: {e}")
            return {"version": "1.0.0", "devices": {}, "brand_rules": {}}

    def _save_knowledge(self):
        """持久化保存知识库"""
        try:
            self.knowledge_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.knowledge_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            logger.info("✅ 设备画像与故障自进化知识库持久化存盘成功")
        except Exception as e:
            logger.error(f"保存设备知识库失败: {e}")

    def get_device_fingerprint(self, device_id: str) -> Dict[str, str]:
        """通过 ADB 提取目标真机的完整软硬件画像"""
        info = {
            "device_id": device_id,
            "brand": "Android",
            "model": "Generic Device",
            "release": "Unknown",
            "rom": "AOSP",
            "rom_version": ""
        }
        if not device_id or device_id in ["mock-device", "local-simulator", "default"]:
            return info

        def _get_prop(prop_name: str) -> str:
            try:
                cmd = [self.adb_bin, "-s", device_id, "shell", "getprop", prop_name]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                return res.stdout.strip()
            except Exception:
                return ""

        brand = _get_prop("ro.product.brand")
        model = _get_prop("ro.product.model")
        release = _get_prop("ro.build.version.release")
        miui_ver = _get_prop("ro.miui.ui.version.name")
        emui_ver = _get_prop("ro.build.version.emui")
        color_ver = _get_prop("ro.build.version.opporom")

        if brand:
            info["brand"] = brand.capitalize()
        if model:
            info["model"] = model
        if release:
            info["release"] = f"Android {release}"

        if miui_ver:
            info["rom"] = "MIUI"
            info["rom_version"] = miui_ver
        elif emui_ver or "harmony" in _get_prop("ro.build.description").lower():
            info["rom"] = "HarmonyOS/EMUI"
            info["rom_version"] = emui_ver
        elif color_ver:
            info["rom"] = "ColorOS"
            info["rom_version"] = color_ver
        elif brand.lower() == "vivo":
            info["rom"] = "OriginOS"

        return info

    def match_knowledge(self, device_info: Dict[str, str], error_text: str) -> Optional[Dict[str, str]]:
        """
        优先查库：根据机型特征与异常日志，在已有知识库中秒级匹配解决方案
        """
        if not error_text:
            return None

        brand = device_info.get("brand", "")
        model = device_info.get("model", "")
        dev_key = f"{brand}_{model}"

        # 1. 优先匹配该具体机型的已知记录
        dev_entry = self._cache.get("devices", {}).get(dev_key)
        if dev_entry and "records" in dev_entry:
            for rec in dev_entry["records"]:
                pat = rec.get("pattern", "")
                if pat and re.search(pat, error_text, re.IGNORECASE):
                    logger.info(f"⚡ [设备知识库命中] 精准匹配到机型 [{dev_key}] 专属排障记录: {rec.get('title')}")
                    return {
                        "source": "device_cache",
                        "title": rec.get("title", ""),
                        "situation": rec.get("situation", ""),
                        "solution": rec.get("solution", "")
                    }

        # 2. 匹配该品牌的通用规则
        brand_entry = self._cache.get("brand_rules", {}).get(brand)
        if brand_entry and "records" in brand_entry:
            for rec in brand_entry["records"]:
                pat = rec.get("pattern", "")
                if pat and re.search(pat, error_text, re.IGNORECASE):
                    logger.info(f"⚡ [品牌知识库命中] 匹配到品牌 [{brand}] 通用规则: {rec.get('title')}")
                    return {
                        "source": "brand_cache",
                        "title": rec.get("title", ""),
                        "situation": rec.get("situation", ""),
                        "solution": rec.get("solution", "")
                    }

        return None

    def probe_input_permission(self, device_id: str) -> Tuple[bool, Optional[str]]:
        """
        前置手势注入安全探针：
        微秒级探测目标手机是否授予了模拟点击/手势注入权限（INJECT_EVENTS）。
        返回: (是否健康可用, 异常错误日志或排查建议)
        """
        if not device_id or device_id in ["mock-device", "local-simulator", "default"]:
            return True, None

        dev_info = self.get_device_fingerprint(device_id)

        try:
            # 清空并监听 logcat
            subprocess.run([self.adb_bin, "-s", device_id, "logcat", "-c"], capture_output=True, timeout=2)
            # 向屏幕发送微秒级无害微步点击
            subprocess.run([self.adb_bin, "-s", device_id, "shell", "input", "tap", "10", "10"], capture_output=True, timeout=3)
            # 抓取最近 30 行日志核查
            res_log = subprocess.run([self.adb_bin, "-s", device_id, "logcat", "-d", "-t", "30"], capture_output=True, text=True, timeout=3)
            log_text = res_log.stdout

            # 校验是否存在权限拒绝
            if re.search(r"INJECT_EVENTS|permission denied.*android\.permission\.INJECT_EVENTS|Input event injection.*permission denied|injecting event.*Permission denied", log_text, re.IGNORECASE):
                logger.error(f"❌ 探针捕获到真机 [{device_id}] 模拟点击权限被系统底层拦截！")
                # 尝试从知识库匹配
                matched = self.match_knowledge(dev_info, log_text)
                if not matched:
                    # 未命中则自动进行 AI 诊断学习
                    matched = self.learn_and_save_issue(dev_info, "手势模拟点击注入被系统底层拦截 (INJECT_EVENTS)", log_text)
                return False, matched.get("solution") if matched else "手机系统限制了 USB 模拟点击，请在开发者选项中开启【USB 调试（安全设置）】。"

            return True, None
        except Exception as e:
            logger.warning(f"执行手势注入探针异常: {e}")
            return True, None

    def learn_and_save_issue(self, device_info: Dict[str, str], error_summary: str, raw_log: str) -> Dict[str, str]:
        """
        AI 自学习核心：当遇到未知错误时，调用大模型进行根因分析与解法推演，并自动存盘更新知识库
        """
        logger.info(f"🧠 [AI 启动自学习] 未知机型故障，正在分析 {device_info.get('brand')} {device_info.get('model')} 的底层异常...")
        brand = device_info.get("brand", "Generic")
        model = device_info.get("model", "Device")
        dev_key = f"{brand}_{model}"

        # 提取关键日志切片，控制 Token
        log_slice = "\n".join(raw_log.strip().split("\n")[-35:])

        system_prompt = """你是一个顶级的 Android 底层自动化测试架构师与定制 ROM 兼容性专家。
你的任务是根据传入的【手机品牌机型】与【报错/崩溃底层日志】，分析导致自动化手势或应用部署受阻的根本原因，并给出让普通测试人员能够对照手机界面完成操作的排查指南。

请以严格的 JSON 格式输出，不要包含 markdown 标记代码块：
{
  "title": "简明问题标题（如：小米系统 USB 模拟点击安全拦截）",
  "situation": "通俗的现状描述（50字以内，讲清楚为什么手机屏幕没反应或被卡住）",
  "solution": "1. 点对点操作步骤（如：进入设置->开发者选项开启某某开关）；\n2. 备用解决指引。"
}
"""

        user_prompt = f"""【设备画像】：
- 品牌: {brand}
- 机型: {model}
- 系统版本: {device_info.get('release', '')}
- 定制 ROM: {device_info.get('rom', '')} {device_info.get('rom_version', '')}

【异常概要】：{error_summary}

【底层关键日志】：
{log_slice}
"""

        diag_result = {
            "source": "ai_learned",
            "title": f"{brand} 手机系统手势/安全策略拦截",
            "situation": f"检测到 {brand} {model} 拦截了自动化测试指令，底层手势或应用服务未能生效。",
            "solution": f"请检查手机【开发者选项】，开启与【USB 调试】、【安全设置】或【允许模拟点击】相关的全部权限开关。"
        }

        try:
            from core.llm_client import LLMClient
            client = LLMClient()
            ai_res = client.chat_decision(system_prompt=system_prompt, user_prompt=user_prompt)
            if isinstance(ai_res, dict) and "title" in ai_res and "solution" in ai_res:
                diag_result["title"] = ai_res.get("title", diag_result["title"])
                diag_result["situation"] = ai_res.get("situation", diag_result["situation"])
                diag_result["solution"] = ai_res.get("solution", diag_result["solution"])
                logger.info(f"✨ AI 自学习推演成功: {diag_result['title']}")
        except Exception as e:
            logger.warning(f"AI 根因自学习分析调用失败，使用规则降级: {e}")

        # 自动持久化保存到本地设备知识库！实现自动化闭环
        try:
            if "devices" not in self._cache:
                self._cache["devices"] = {}
            if dev_key not in self._cache["devices"]:
                self._cache["devices"][dev_key] = {
                    "brand": brand,
                    "model": model,
                    "rom": device_info.get("rom", ""),
                    "records": []
                }

            # 提取特征关键字
            pattern_kw = "INJECT_EVENTS" if "INJECT_EVENTS" in log_slice else "permission denied|failed|error"
            new_record = {
                "issue_key": f"auto_{int(Path(__file__).stat().st_mtime)}_{brand.lower()}",
                "pattern": pattern_kw,
                "title": diag_result["title"],
                "situation": diag_result["situation"],
                "solution": diag_result["solution"]
            }

            self._cache["devices"][dev_key]["records"].append(new_record)
            self._save_knowledge()
            logger.info(f"🎉 成功将新学习到的机型规则沉淀至本地知识库: [{dev_key}]")
        except Exception as e:
            logger.warning(f"沉淀自学习规则存盘异常: {e}")

        return diag_result

# 全局单例
device_knowledge_mgr = DeviceKnowledgeManager()
