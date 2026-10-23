"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 进入象盒找房二手房列表，设置区域筛选为岳麓区
生成时间: 自动化录制后生成
执行方式: pytest test_auto_flow.py -v -s
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
@allure.story("进入象盒找房二手房列表，设置区域筛选为岳麓区")
def test_test_auto_flow(driver, api_client):
    """
    自动化用例: test_auto_flow
    进入象盒找房二手房列表，设置区域筛选为岳麓区
    """
    # 步骤 1: 点击首页的二手房图标进入二手房列表页 (坐标点击)
    driver.tap([(336, 395)])
    time.sleep(1)

    # 步骤 2: 点击区域筛选下拉菜单 (坐标点击)
    driver.tap([(142, 577)])
    time.sleep(1)

    # 步骤 3: 在区域筛选列表中选择岳麓区 (坐标点击)
    driver.tap([(648, 1126)])
    time.sleep(1)

    # 步骤 4: 点击确定按钮应用岳麓区筛选条件 (坐标点击)
    driver.tap([(746, 1876)])
    time.sleep(1)
