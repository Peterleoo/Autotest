# -*- coding: utf-8 -*-
r"""
端到端用户旅程套件与用例智能合成引擎 (User Journey Synthesizer)
对标移动端业务测试全生命周期标准：
1. 应用领域智能感知 (App Domain Perception)
2. 3 大端到端角色化业务旅程套件 (Journey Suites: Onboarding / Core Conversion / Edge Validation)
3. 场景化单点精选测试用例动态派发
"""

import re
from typing import Dict, Any, List, Optional

class JourneySynthesizer:
    """端到端用户旅程套件合成器"""

    DOMAIN_KEYWORDS = {
        "real_estate": ["房", "安居客", "贝壳", "链家", "二手房", "租房", "楼盘", "置业", "中介", "经纪人", "anjuke", "lianjia", "ke"],
        "ecommerce": ["买", "淘", "京东", "拼多多", "唯品会", "购物车", "商城", "商品", "零售", "订单", "taobao", "jd", "pdd"],
        "social": ["聊", "信", "社交", "微信", "微博", "社区", "好友", "动态", "朋友圈", "wechat", "weibo"],
        "media_music": ["音", "视频", "播放", "影", "歌", "影视", "音乐", "点播", "music", "video", "bilibili", "douyin"],
        "office_tool": ["文档", "办公", "邮件", "盘", "工具", "日历", "便签", "task", "mail", "drive", "wps"]
    }

    @staticmethod
    def infer_app_domain(app_identifier: str) -> str:
        """根据应用名或包名精准推断业务领域"""
        text = str(app_identifier).lower()
        for domain, keywords in JourneySynthesizer.DOMAIN_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return domain
        return "general"

    @staticmethod
    def generate_journey_suites(app_name: str, package_name: str = "") -> List[Dict[str, Any]]:
        """合成 3 大标准化角色化端到端业务旅程套件"""
        domain = JourneySynthesizer.infer_app_domain(f"{app_name} {package_name}")
        clean_app = app_name or "待测应用"

        if domain == "real_estate":
            core_goal = f"在【{clean_app}】首页点击顶部搜索框，输入'精装两居'，触发搜索进入列表页滑动加载，点击首项房源进入详情页并验证总价、户型与微聊咨询窗口弹出。"
            core_stages = ["搜索'精装两居'", "列表下拉刷新与滑动加载", "详情页总价/户型/微聊核验"]
            edge_goal = f"在【{clean_app}】中进入房东委托或信息发布页面，未填必填项直接点击'免费发布'，验证表单必填校验拦截；随后输入特殊字符搜索，验证无结果降级提示。"
            edge_stages = ["空表单必填校验拦截", "特殊字符边界测试", "无结果降级兜底提示"]
        elif domain == "ecommerce":
            core_goal = f"在【{clean_app}】首页搜索栏输入'无线降噪耳机'，进入搜索结果列表，按销量排序后点击首个商品进入商详页，选择规格加入购物车并断言提示。"
            core_stages = ["搜索核心商品", "销量榜单列表排序", "商品规格选择与加购断言"]
            edge_goal = f"在【{clean_app}】中测试收货地址新增与结算表单，留空手机号直接提交，验证表单校验拦截，并测试极端长字符输入防溢出。"
            edge_stages = ["地址表单必填项校验", "超长字符溢出测试", "网络弱网降级提示"]
        elif domain == "social":
            core_goal = f"在【{clean_app}】首页浏览消息与动态信息流，点击进入首个对话窗口输入测试文字并发送，返回主页切换至个人中心核对资料。"
            core_stages = ["信息流浏览与触达", "消息会话输入与发送", "个人中心页面状态核对"]
            edge_goal = f"在【{clean_app}】发布动态或设置页面，不输入任何文字直接点击发布，验证空态拦截并测试隐私设置切换的持久化保存。"
            edge_stages = ["空内容发布拦截", "特殊符号过滤校验", "隐私设置开关状态校验"]
        else:
            core_goal = f"冷启动【{clean_app}】，在主界面导航金刚区点击核心业务频道，执行长列表平滑滑动浏览，点击关键内容项进入二级详情页并断言界面渲染完成。"
            core_stages = ["首页核心频道直达", "信息流列表滑动加载", "二级详情页完整性断言"]
            edge_goal = f"在【{clean_app}】各输入与表单页面进行边界值校验，测试空字符提交、超长文本与快速连续手势，验证应用运行稳定无闪退崩溃。"
            edge_stages = ["空值提交边界拦截", "快速连击防抖测试", "深层界面返回导航闭环"]

        suites = [
            {
                "id": "suite_onboarding",
                "title": "初访与权限激活旅程",
                "badge": "冷启动链路",
                "badge_class": "badge-activation",
                "summary": "走通应用冷启动、隐私协议确认、引导页穿透直达首页",
                "goal": f"冷启动【{clean_app}】，若弹出隐私服务协议勾选同意，快速穿透引导轮播图直达应用主页，断言主导航 Tab 与主框架正常就绪。",
                "stages": ["冷启动与权限申请", "隐私政策同意与引导页跳过", "首页主导航与骨架屏就绪"]
            },
            {
                "id": "suite_core_conversion",
                "title": "核心主线业务旅程",
                "badge": "P0 主干链路",
                "badge_class": "badge-core",
                "summary": "贯通核心价值流（检索 ➔ 级联筛选 ➔ 详情流转 ➔ 意向交互）",
                "goal": core_goal,
                "stages": core_stages
            },
            {
                "id": "suite_edge_resilience",
                "title": "逆向异常与表单防御旅程",
                "badge": "健壮性防御",
                "badge_class": "badge-edge",
                "summary": "针对空值拦截、长文本溢出、无结果降级兜底进行全面防守核验",
                "goal": edge_goal,
                "stages": edge_stages
            }
        ]
        return suites

    @staticmethod
    def generate_single_cases(app_name: str, package_name: str = "") -> List[Dict[str, Any]]:
        """根据领域生成 4 个精选单点场景用例"""
        domain = JourneySynthesizer.infer_app_domain(f"{app_name} {package_name}")
        clean_app = app_name or "待测应用"

        if domain == "real_estate":
            return [
                {
                    "id": "CASE-01",
                    "module": "房源检索",
                    "title": "首页房源关键词搜索与筛选交互测试",
                    "goal": f"进入【{clean_app}】首页，在顶部搜索栏输入'精装两居'，触发搜索，进入列表进行滑动加载，断言房源结果正常返回",
                    "level": "P0"
                },
                {
                    "id": "CASE-02",
                    "module": "微聊咨询",
                    "title": "房源详情页浏览与经纪人在线微聊交互",
                    "goal": f"在【{clean_app}】首页点击第一套推荐房源，进入房源详情页查看总价与户型，点击'微聊/咨询'，验证咨询窗口正确弹出",
                    "level": "P0"
                },
                {
                    "id": "CASE-03",
                    "module": "多级筛选",
                    "title": "二手房区域多级联动筛选与价格排序",
                    "goal": f"点击【{clean_app}】'二手房'频道，点击'区域'筛选热门商圈，排序选择'总价从低到高'，验证列表按照价格升序更新",
                    "level": "P1"
                },
                {
                    "id": "CASE-04",
                    "module": "在线委托",
                    "title": "在线委托卖房表单必填项防御拦截",
                    "goal": f"进入【{clean_app}】委托售房页面，留空小区与售价直接点击'免费发布'，验证页面正确触发必填红字提示",
                    "level": "P1"
                }
            ]
        elif domain == "ecommerce":
            return [
                {
                    "id": "CASE-01",
                    "module": "商品搜索",
                    "title": "爆款商品关键词搜索与联想词匹配",
                    "goal": f"在【{clean_app}】搜索框输入'机械键盘'，验证联想词弹出，点击首条联想词进入搜索结果并断言商品价格",
                    "level": "P0"
                },
                {
                    "id": "CASE-02",
                    "module": "商详加购",
                    "title": "商品详情页浏览与规格选择加购",
                    "goal": f"在【{clean_app}】点击首款商品进入商详页，点击'加入购物车'弹出规格选择面板，选择默认型号后点击确认",
                    "level": "P0"
                },
                {
                    "id": "CASE-03",
                    "module": "购物车结算",
                    "title": "购物车勾选计算与结算页流转",
                    "goal": f"进入【{clean_app}】购物车，勾选单件商品验证底部总价动态更新，点击'去结算'验证订单确认页正常加载",
                    "level": "P1"
                },
                {
                    "id": "CASE-04",
                    "module": "地址管理",
                    "title": "新增收货地址表单格式与手机号校验",
                    "goal": f"进入【{clean_app}】收货地址管理，点击添加新地址，输入错误格式手机号提交，验证表单提示'手机号码格式不正确'",
                    "level": "P1"
                }
            ]
        else:
            return [
                {
                    "id": "CASE-01",
                    "module": "冷启动体验",
                    "title": "应用冷启动与主页核心组件可用性",
                    "goal": f"冷启动【{clean_app}】，穿透引导页直达主界面，断言底部 Tab 与主要功能导航正常展示并可点击",
                    "level": "P0"
                },
                {
                    "id": "CASE-02",
                    "module": "信息流浏览",
                    "title": "主页信息流下拉刷新与连滑加载",
                    "goal": f"在【{clean_app}】主界面执行下拉刷新手势，随后连续向上滑动两屏，验证列表无卡顿且数据动态追加",
                    "level": "P0"
                },
                {
                    "id": "CASE-03",
                    "module": "搜索定位",
                    "title": "站内搜索功能与搜索历史流转",
                    "goal": f"在【{clean_app}】搜索框输入测试关键词触发搜索，验证结果列表正常展示，返回后核对搜索历史标签生成",
                    "level": "P1"
                },
                {
                    "id": "CASE-04",
                    "module": "设置与退出",
                    "title": "个人中心与系统设置入口遍历",
                    "goal": f"点击【{clean_app}】'我的'或'设置'，进入个人中心核对版本号信息，点击返回测试多级界面导航回退正常",
                    "level": "P1"
                }
            ]
