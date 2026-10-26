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
        """根据 app_id、package 或文件名模糊查询最佳凭证"""
        if not app_identifier:
            return None
        data = cls._load_data()
        clean_key = app_identifier.lower().replace(".apk", "").strip()

        # 1. 精确匹配
        if clean_key in data:
            return data[clean_key]

        # 2. 模糊包含匹配
        for k, v in data.items():
            if k in clean_key or clean_key in k:
                return v
        return None

    @classmethod
    def set_credential(cls, app_identifier: str, account: str, password: str) -> Dict[str, Any]:
        """保存或更新特定应用的测试账号与密码"""
        if not app_identifier:
            return {}
        data = cls._load_data()
        clean_key = app_identifier.lower().replace(".apk", "").strip()

        record = {
            "account": account.strip(),
            "password": password.strip(),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        data[clean_key] = record
        cls._save_data(data)
        logger.info(f"✅ 已成功更新应用 [{clean_key}] 的测试凭证: 账号={account}")
        return record

    @classmethod
    def list_all(cls) -> Dict[str, Any]:
        return cls._load_data()
