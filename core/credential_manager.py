import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger("CredentialManager")

CREDENTIALS_FILE = Path(__file__).resolve().parent.parent / "apps" / "credentials.json"

class CredentialManager:
    """
    轻量级待测应用账号凭证管理中心 (Credential Vault)
    负责存储与查询各 App 的测试账号密码，支撑人机协同自动回填与免打扰无人值守测试。
    """
    
    @classmethod
    def _load_data(cls) -> Dict[str, Any]:
        if not CREDENTIALS_FILE.exists():
            return {}
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"读取凭证文件失败: {e}")
            return {}

    @classmethod
    def _save_data(cls, data: Dict[str, Any]):
        try:
            CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"写入凭证文件失败: {e}")

    @classmethod
    def get_credential(cls, app_identifier: str) -> Optional[Dict[str, str]]:
        """根据 app_id、package 或文件名模糊查询最佳凭证，支持多别名穿透与兜底"""
        data = cls._load_data()
        if not data:
            return None

        if not app_identifier:
            # 若未指定应用，优先返回最新一条有效凭证
            sorted_items = sorted(data.values(), key=lambda x: x.get("updated_at", ""), reverse=True)
            return sorted_items[0] if sorted_items else None

        clean_key = app_identifier.lower().replace(".apk", "").strip()

        # 1. 精确匹配
        if clean_key in data:
            return data[clean_key]

        # 2. 别名与包名归一化匹配 (例如 xianghe_zhaofang <=> com.apicloud.A6995433058179)
        known_alias_groups = [
            {"xianghe_zhaofang", "com.apicloud.a6995433058179", "象盒找房", "zhaofang"},
            {"xianghe_workbench", "com.xhj.workbench", "象盒工作台", "workbench"}
        ]
        for group in known_alias_groups:
            if any(alias in clean_key for alias in group):
                for member in group:
                    if member in data:
                        return data[member]

        # 3. 模糊包含匹配
        for k, v in data.items():
            if k in clean_key or clean_key in k:
                return v

        # 4. 兜底返回最新有效凭证
        if "demo_app" in data:
            return data["demo_app"]
        sorted_items = sorted(data.values(), key=lambda x: x.get("updated_at", ""), reverse=True)
        return sorted_items[0] if sorted_items else None

    @classmethod
    def set_credential(cls, app_identifier: str, account: str, password: str) -> Dict[str, Any]:
        """保存或更新特定应用的测试账号与密码，自动进行别名群组多向同步"""
        if not app_identifier:
            app_identifier = "demo_app"
        data = cls._load_data()
        clean_key = app_identifier.lower().replace(".apk", "").strip()

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "account": account.strip(),
            "password": password.strip(),
            "updated_at": now_str
        }
        data[clean_key] = record

        # 自动多向同步到已知别名群组
        known_alias_groups = [
            {"xianghe_zhaofang", "com.apicloud.a6995433058179", "象盒找房"},
            {"xianghe_workbench", "com.xhj.workbench", "象盒工作台"}
        ]
        for group in known_alias_groups:
            if any(alias in clean_key for alias in group):
                for member in group:
                    data[member] = record

        # 同时也保留通用兜底
        data["demo_app"] = record

        cls._save_data(data)
        logger.info(f"✅ 已成功更新应用 [{clean_key}] 及关联别名的测试凭证: 账号={account}")
        return record

    @classmethod
    def list_all(cls) -> Dict[str, Any]:
        return cls._load_data()
