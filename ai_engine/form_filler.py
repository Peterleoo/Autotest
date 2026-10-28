import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("SmartFormFiller")

class SmartFormFiller:
    """
    轻量级表单智能推断引擎 (Smart Form Filler)
    1. 90% 常规字段全自动推断：姓名、手机号、期望售价、建筑面积、小区名称、短信验证码等；
    2. 毫秒级规则匹配，0 Token 开销，合规数据即刻上屏；
    3. 特殊/高敏感字段标记（仅 10% 无法决断时留出人机协助插槽）。
    """

    # 默认合规基线测试数据集
    DEFAULT_PRESETS = {
        "mobile": "13800138000",
        "name": "张先生",
        "price": "300",          # 期望售价 300万 / 租金 3500元
        "rent_price": "3500",
        "area": "98",             # 建筑面积 98㎡
        "community": "阳光花园",   # 通用示例小区
        "code": "123456",
        "email": "test_qa@example.com",
    }

    @classmethod
    def infer_value(cls, el_info: Optional[Dict[str, Any]], goal: str = "", raw_text: str = "", app_identifier: Optional[str] = None) -> str:
        """
        根据元素上下文、目标描述及原有文本智能推断最佳上屏数据，优先读取 App 预置真实凭证
        """
        # 如果已经传入了有效具体的业务值（非占位符），直接使用
        if raw_text and not cls._is_placeholder(raw_text):
            return raw_text

        context_str = cls._extract_context(el_info, raw_text)

        # 0. 尝试获取该应用配置的真实测试凭证
        app_cred = None
        if app_identifier:
            try:
                from core.credential_manager import CredentialManager
                app_cred = CredentialManager.get_credential(app_identifier)
            except Exception:
                pass
        
        # 1. 手机号 / 联系方式 / 账号 / 登录码
        if re.search(r"手机|电话|联系方式|联系电话|mobile|phone|账号|用户名|登录码|工号|合伙人", context_str, re.I):
            if app_cred and app_cred.get("account"):
                logger.info(f"🔑 [智能表单] 命中真实测试账号，应用预置凭证: {app_cred['account']}")
                return app_cred["account"]
            # 🛡️ 严格防瞎编铁律：若是登录/鉴权界面且无预设凭证，严禁捏造假号码，交由人机协同输入！
            if re.search(r"登录|账号|密码|工号|合伙人|鉴权|注册", context_str, re.I):
                logger.warning("🛡️ [智能表单防瞎编] 当前属于登录鉴权输入框且无预设凭证，严禁瞎编假号码！")
                return ""
            logger.info(f"💡 [智能表单] 命中业务联系方式规则，填充基线测试号: {cls.DEFAULT_PRESETS['mobile']}")
            return cls.DEFAULT_PRESETS["mobile"]

        # 1.1 密码
        if re.search(r"密码|口令|password|pwd", context_str, re.I):
            if app_cred and app_cred.get("password"):
                logger.info(f"🔑 [智能表单] 命中真实测试密码，应用预置凭证")
                return app_cred["password"]
            # 🛡️ 严格防瞎编铁律：严禁捏造虚假密码
            logger.warning("🛡️ [智能表单防瞎编] 密码字段未配置有效真实凭证，严禁填入虚假密码！")
            return ""

        # 2. 姓名 / 称呼 / 联系人
        if re.search(r"称呼|姓名|联系人|业主姓名|房东|name", context_str, re.I):
            logger.info(f"💡 [智能表单] 命中姓名/称呼规则，自动填充: {cls.DEFAULT_PRESETS['name']}")
            return cls.DEFAULT_PRESETS["name"]

        # 3. 租金 / 售价 / 期望售价 / 价格
        if re.search(r"租金|月租", context_str, re.I):
            logger.info(f"💡 [智能表单] 命中租金规则，自动填充: {cls.DEFAULT_PRESETS['rent_price']}")
            return cls.DEFAULT_PRESETS["rent_price"]
        if re.search(r"售价|期望售价|总价|金额|价格|price", context_str, re.I):
            logger.info(f"💡 [智能表单] 命中售价规则，自动填充: {cls.DEFAULT_PRESETS['price']}")
            return cls.DEFAULT_PRESETS["price"]

        # 4. 建筑面积 / 面积
        if re.search(r"面积|平米|m²|平方|area", context_str, re.I):
            logger.info(f"💡 [智能表单] 命中面积规则，自动填充: {cls.DEFAULT_PRESETS['area']}")
            return cls.DEFAULT_PRESETS["area"]

        # 5. 小区名称 / 楼盘
        if re.search(r"小区|楼盘|物业名称|房源位置|community", context_str, re.I):
            # 优先从用户的测试目标中提取具体小区（如“华润凤凰城”、“钰龙天下”）
            match = re.search(r"['\"]?([^\s,，。、]+?(?:小区|家园|天下|花园|城|苑|公馆|国际|村|湾))['\"]?", goal)
            if match:
                extracted = re.sub(r'^(在|于|去|进入|到|测试)', '', match.group(1).strip("'\""))
                logger.info(f"💡 [智能表单] 从用户目标提取小区名，自动填充: {extracted}")
                return extracted
            return cls.DEFAULT_PRESETS["community"]

        # 6. 验证码
        if re.search(r"验证码|动态码|code", context_str, re.I):
            return cls.DEFAULT_PRESETS["code"]

        # 默认兜底
        return raw_text or "测试数据"

    @classmethod
    def is_sensitive_or_ambiguous(cls, el_info: Optional[Dict[str, Any]]) -> bool:
        """
        判断是否属于必须由人工决断的特殊/敏感字段（10% 范畴）
        如身份证、银行卡、动态人脸、共有产权二选一、抵押状况二选一
        """
        context_str = cls._extract_context(el_info, "")
        if re.search(r"身份证|银行卡|动态人脸|活体|共有产权|抵押贷款|房产证号", context_str, re.I):
            return True
        return False

    @staticmethod
    def _is_placeholder(val: str) -> bool:
        """判断是否为占位符文本"""
        if not val:
            return True
        val_clean = val.strip().lower()
        return val_clean in [
            "auto", "{phone}", "{mobile}", "{name}", "{price}", "{area}",
            "请输入", "输入", "请填写", "填写", "请输入售价", "请输入姓名", "请输入手机号"
        ]

    @staticmethod
    def _extract_context(el_info: Optional[Dict[str, Any]], raw_text: str) -> str:
        if not el_info:
            return raw_text or ""
        txt = el_info.get("text", "") or ""
        desc = el_info.get("desc", "") or ""
        r_id = el_info.get("resource-id", "") or ""
        return f"{txt} {desc} {r_id} {raw_text}".strip()
