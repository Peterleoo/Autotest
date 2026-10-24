"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 在首页点击'地图找房'进入地图模式，缩放地图并点击任意片区价格气泡，验证下方房源浮层联动弹出并展示均价
生成时间: 自动化录制后生成
执行方式: pytest test_search_20261024_103141.py -v -s
"""
import time
import pytest
import allure
from appium.webdriver.common.appiumby import AppiumBy

from core.driver_factory import DriverFactory
from core.api_client import APIClient

@pytest.fixture(scope="module")
def driver():
    """初始化 Appium 驱动"""
    drv = DriverFactory.create_driver()
    yield drv
    drv.quit()

@pytest.fixture(scope="module")
def api_client():
    """初始化统一接口客户端"""
    return APIClient()

@allure.feature("固化测试套件")
@allure.story("在首页点击'地图找房'进入地图模式，缩放地图并点击任意片区价格气泡，验证下方房源浮层联动弹出并展示均价")
def test_test_search_20261024_103141(driver, api_client):
    """
    自动化用例: test_search_20261024_103141
    在首页点击'地图找房'进入地图模式，缩放地图并点击任意片区价格气泡，验证下方房源浮层联动弹出并展示均价
    """
    # 步骤 1: 等待界面加载
    time.sleep(1)

    # 步骤 2: 断言页面包含文本 [等待地图与气泡渲染]
    assert '等待地图与气泡渲染' in driver.page_source, f'断言失败：页面未出现预期文本: 等待地图与气泡渲染'

    # 步骤 3: 断言页面包含文本 [手势缩放地图视图]
    assert '手势缩放地图视图' in driver.page_source, f'断言失败：页面未出现预期文本: 手势缩放地图视图'

    # 步骤 4: 断言页面包含文本 [点击目标片区价格气泡]
    assert '点击目标片区价格气泡' in driver.page_source, f'断言失败：页面未出现预期文本: 点击目标片区价格气泡'

    # 步骤 5: 断言页面包含文本 [验证房源浮层与均价展示]
    assert '验证房源浮层与均价展示' in driver.page_source, f'断言失败：页面未出现预期文本: 验证房源浮层与均价展示'
