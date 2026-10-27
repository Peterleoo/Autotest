import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("AppLessonsManager")

BASE_DIR = Path(__file__).resolve().parent.parent
LESSONS_FILE = BASE_DIR / "data" / "app_lessons.json"

class AppLessonsManager:
    """
    应用级踩坑经验与寻路知识库管理器 (App Lessons Engine)
    1. 跨会话沉淀各 App 独有的导航规律、金刚区滑动特征与表单避坑经验；
    2. 意图拆解与测试执行前 0 Token 毫秒级提取并注入 Agent Prompt；
    3. 支持新探索路径自动归纳并持久化存盘。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AppLessonsManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        self.lessons_path = LESSONS_FILE
        self._data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        if not self.lessons_path.exists():
            return {"version": "1.0.0", "apps": {}}
        try:
            with open(self.lessons_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载应用经验库失败: {e}")
            return {"version": "1.0.0", "apps": {}}

    def _save_data(self):
        try:
            self.lessons_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.lessons_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            logger.info("✅ 应用避坑与寻路经验库持久化保存成功")
        except Exception as e:
            logger.error(f"保存应用经验库失败: {e}")

    def get_matched_lessons(self, app_id: str, goal: str = "") -> List[str]:
        """
        根据当前待测 App 包名/标识与目标，提取匹配的专家经验条目
        """
        matched = []
        apps = self._data.get("apps", {})
        
        # 兼容模糊匹配包名或 App 名称（如 com.example.app 或 待测应用）
        app_entry = None
        for key, val in apps.items():
            if key in app_id or app_id in key or val.get("app_name", "") in app_id or val.get("app_name", "") in goal:
                app_entry = val
                break
        
        if not app_entry:
            # 默认兜底：若未精确匹配，取通用示例规则组
            app_entry = apps.get("demo_app") or (next(iter(apps.values())) if apps else None)

        if app_entry:
            for item in app_entry.get("lessons", []):
                kws = item.get("keywords", [])
                if not kws or any(kw in goal for kw in kws):
                    matched.append(item.get("experience", ""))

        return matched

    def record_new_lesson(self, app_id: str, tag: str, keywords: List[str], experience: str):
        """记录新的自愈经验并持久化"""
        apps = self._data.setdefault("apps", {})
        entry = apps.setdefault(app_id, {"app_name": app_id, "lessons": []})
        
        # 检查是否已有相同 tag
        for existing in entry["lessons"]:
            if existing.get("tag") == tag:
                existing["experience"] = experience
                existing["keywords"] = list(set(existing.get("keywords", []) + keywords))
                self._save_data()
                return

        entry["lessons"].append({
            "tag": tag,
            "keywords": keywords,
            "experience": experience
        })
        self._save_data()

app_lessons_mgr = AppLessonsManager()
