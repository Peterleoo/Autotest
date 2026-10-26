import time
import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("DeliverablesManager")

BASE_DIR = Path(__file__).resolve().parent.parent
DELIVERABLES_FILE = BASE_DIR / ".pm" / "deliverables.json"

class DeliverablesManager:
    """
    与 PM-product ProductOS 原生对齐的交付物注册表管理器
    1. 负责读写 .pm/deliverables.json；
    2. 将自动化测试生成的 Python 回归脚本自动注册为正式 'Validation' 交付物；
    3. 支持 0 Token 毫秒级原生回放与状态更新。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DeliverablesManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        self.file_path = DELIVERABLES_FILE

    def _read_manifest(self) -> Dict[str, Any]:
        if not self.file_path.exists():
            return {"version": 1, "updatedAt": datetime.now(timezone.utc).isoformat(), "deliverables": []}
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"读取 .pm/deliverables.json 异常: {e}")
            return {"version": 1, "updatedAt": datetime.now(timezone.utc).isoformat(), "deliverables": []}

    def _write_manifest(self, data: Dict[str, Any]):
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            data["updatedAt"] = datetime.now(timezone.utc).isoformat()
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("✅ 交付物注册表 .pm/deliverables.json 成功存盘")
        except Exception as e:
            logger.error(f"写入 .pm/deliverables.json 失败: {e}")

    def list_deliverables(self) -> List[Dict[str, Any]]:
        manifest = self._read_manifest()
        return manifest.get("deliverables", [])

    def register_test_script(self, script_relative_path: str, title: str, case_id: Optional[str] = None) -> Dict[str, Any]:
        """将固化生成的测试用例注册到 .pm/deliverables.json (Category: 验证 / Validation)"""
        manifest = self._read_manifest()
        deliverables = manifest.setdefault("deliverables", [])
        
        cid = case_id or Path(script_relative_path).stem
        now_iso = datetime.now(timezone.utc).isoformat()

        # 检查是否已存在
        for item in deliverables:
            if item.get("id") == cid or item.get("safeRef") == script_relative_path:
                item["title"] = title
                item["safeRef"] = script_relative_path
                item["status"] = "generated"
                item["updatedAt"] = now_iso
                self._write_manifest(manifest)
                logger.info(f"✔ 交付物已更新: {cid} -> {script_relative_path}")
                return item

        new_entry = {
            "id": cid,
            "title": title,
            "safeRef": script_relative_path,
            "status": "generated",
            "contentChanged": False,
            "category": "验证",
            "categoryPriority": 60,
            "productOsNode": "validation",
            "dependsOn": [],
            "updatedAt": now_iso
        }
        deliverables.append(new_entry)
        self._write_manifest(manifest)
        logger.info(f"✔ 交付物已成功注册至 .pm/deliverables.json: {cid}")
        return new_entry

deliverables_mgr = DeliverablesManager()
