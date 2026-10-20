"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 遍历首页金刚区各入口，并依次切换底部导航栏各一级 Tab
生成时间: 自动化录制后生成
执行方式: pytest test_matrix_flow.py -v -s
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
@allure.story("遍历首页金刚区各入口，并依次切换底部导航栏各一级 Tab")
def test_test_matrix_flow(driver, api_client):
    """
    自动化用例: test_matrix_flow
    遍历首页金刚区各入口，并依次切换底部导航栏各一级 Tab
    """
    # 步骤 1: 点击首页金刚区【租房】入口进入租房业务页面 (坐标点击)
    driver.tap([(133, 414)])
    time.sleep(1)

    # 步骤 2: 点击左上角返回按钮返回首页 (坐标点击)
    driver.tap([(80, 165)])
    time.sleep(1)

    # 步骤 3: 点击首页金刚区【二手房】入口 (坐标点击)
    driver.tap([(336, 414)])
    time.sleep(1)

    # 步骤 4: 点击左上角返回按钮返回首页继续遍历金刚区其他入口 (坐标点击)
    driver.tap([(82, 165)])
    time.sleep(1)

    # 步骤 5: 点击首页金刚区【新房】入口进入新房业务页面 (坐标点击)
    driver.tap([(539, 414)])
    time.sleep(1)

    # 步骤 6: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 7: 点击左上角返回按钮退出新房频道返回首页 (坐标点击)
    driver.tap([(84, 165)])
    time.sleep(1)

    # 步骤 8: 点击首页金刚区【写字楼】入口进入写字楼频道页面进行测试 (坐标点击)
    driver.tap([(743, 414)])
    time.sleep(1)

    # 步骤 9: 点击左上角返回按钮退出写字楼频道返回首页 (坐标点击)
    driver.tap([(84, 165)])
    time.sleep(1)
