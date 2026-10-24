"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 搜索望京两居室，筛选租金5000-8000并断言第一条房源信息
生成时间: 自动化录制后生成
执行方式: pytest test_general_20261020_161034.py -v -s
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
@allure.story("搜索望京两居室，筛选租金5000-8000并断言第一条房源信息")
def test_test_general_20261020_161034(driver, api_client):
    """
    自动化用例: test_general_20261020_161034
    搜索望京两居室，筛选租金5000-8000并断言第一条房源信息
    """
    # 步骤 1: 等待界面加载
    time.sleep(1)

    # 步骤 2: 断言页面包含文本 [定位业务频道入口]
    assert '定位业务频道入口' in driver.page_source, f'断言失败：页面未出现预期文本: 定位业务频道入口'

    # 步骤 3: 断言页面包含文本 [激活搜索并注入检索词]
    assert '激活搜索并注入检索词' in driver.page_source, f'断言失败：页面未出现预期文本: 激活搜索并注入检索词'

    # 步骤 4: 断言页面包含文本 [列表异步加载与断言]
    assert '列表异步加载与断言' in driver.page_source, f'断言失败：页面未出现预期文本: 列表异步加载与断言'

    # 步骤 5: 断言页面包含文本 [回归脚本固化与归档]
    assert '回归脚本固化与归档' in driver.page_source, f'断言失败：页面未出现预期文本: 回归脚本固化与归档'
