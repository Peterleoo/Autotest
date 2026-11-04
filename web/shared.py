# -*- coding: utf-8 -*-
"""Web 层共享对象：路径常量、全局管理器单例与跨路由复用的辅助函数"""
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("WebApp")

# 添加工程根目录到 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config.settings import settings
from core.app_manager import AppManager
from core.report_generator import REPORTS_DIR
from core.task_manager import TaskManager
from core.screen_stream_hub import screen_stream_hub


# 多模态需求资产上传与缓存目录
UPLOADS_DIR = BASE_DIR / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# 挂载测试报告静态目录
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

app_mgr = AppManager()
screen_stream_hub.set_adb_bin(app_mgr.adb_bin)
task_mgr = TaskManager()


def resolve_target_device_id(preferred_id: Optional[str] = None) -> Optional[str]:
    """动态解析当前真实在线的目标真机 ID (杜绝硬编码设备序列号导致的脱靶)"""
    try:
        connected = app_mgr.get_connected_devices()
        conn_ids = [d.get("id") if isinstance(d, dict) else d for d in connected if d]
    except Exception:
        conn_ids = []

    if not conn_ids:
        return None

    # 若指定了有效在线设备且在当前在线列表中，直接使用
    if preferred_id and preferred_id not in ["mock-device", "local-simulator", "default", "auto"]:
        if preferred_id in conn_ids:
            return preferred_id

    # 否则自动平滑对齐至当前首选在线真机
    return conn_ids[0]


ALL_SUGGESTED_CASES = [
    {
        "id": "CASE-01",
        "module": "房源检索与搜索",
        "title": "首页房源关键词搜索与筛选交互测试",
        "goal": "进入首页，在顶部搜索栏输入'精装两居'，触发搜索，进入搜索结果列表进行下拉滑动加载，并断言列表包含房源信息",
        "level": "P0"
    },
    {
        "id": "CASE-02",
        "module": "热门小区直达",
        "title": "热门小区快速检索与详情流转",
        "goal": "进入首页，点击顶部搜索栏，输入或点击热门小区'钰龙天下'，触发搜索进入房源列表，滑动查看并断言房源结果",
        "level": "P0"
    },
    {
        "id": "CASE-03",
        "module": "账号与隐私鉴权",
        "title": "用户验证码/密码登录与协议同意流程",
        "goal": "打开应用，若有隐私政策点击同意，进入登录界面输入账号密码，测试登录跳转并断言鉴权接口返回 200",
        "level": "P0"
    },
    {
        "id": "CASE-04",
        "module": "房源详情与微聊",
        "title": "房源详情页浏览与经纪人在线微聊交互",
        "goal": "在首页点击第一套推荐房源，进入房源详情页查看总价、户型与VR看房标识，点击'微聊/咨询'按钮，验证咨询窗口正确弹出",
        "level": "P1"
    },
    {
        "id": "CASE-05",
        "module": "二手房频道与筛选",
        "title": "二手房区域多级联动筛选与排序测试",
        "goal": "点击底部或首页'二手房'入口，进入列表后点击'区域'筛选'岳麓区'，排序选择'总价从低到高'，验证列表已按照价格排序更新",
        "level": "P1"
    },
    {
        "id": "CASE-06",
        "module": "品质租房频道",
        "title": "整租/合租快速切换与整租列表加载",
        "goal": "在首页点击'租房'进入租房主频道，点击'整租'标签进行切换，向下滑动加载两屏房源，断言月租金与户型信息展示完备",
        "level": "P1"
    },
    {
        "id": "CASE-07",
        "module": "线上委托业务",
        "title": "房东在线委托卖房与表单验证",
        "goal": "进入'委托服务'页面，点击'委托售房'，验证小区名称、期望售价与联系方式表单项正常渲染，并点击'免费发布'测试必填校验",
        "level": "P2"
    },
    {
        "id": "CASE-08",
        "module": "地图找房与测距",
        "title": "地图找房模式加载与区域气泡交互",
        "goal": "在首页点击'地图找房'进入地图模式，缩放地图并点击任意片区价格气泡，验证下方房源浮层联动弹出并展示均价",
        "level": "P2"
    }
]

METADATA_FILE = settings.SOLIDIFIED_DIR / "cases_metadata.json"

KNOWN_APP_META = {
    "xianghe_zhaofang": {
        "name": "象盒找房",
        "package": "com.apicloud.A6995433058179",
        "version": "真机已安装",
    },
    "xianghe_workbench": {
        "name": "象盒工作台",
        "package": "com.xhj.workbench",
        "version": "真机已安装",
    },
    "demo_app": {
        "name": "待测示例应用",
        "package": "com.autotest.demo",
        "version": "v1.0.0",
    }
}
