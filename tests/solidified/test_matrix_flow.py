"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 重新开始
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
@allure.story("重新开始")
def test_test_matrix_flow(driver, api_client):
    """
    自动化用例: test_matrix_flow
    重新开始
    """
    # 步骤 1: 点击底部首页Tab，刷新并回到首页起始状态 (坐标点击)
    driver.tap([(135, 2019)])
    time.sleep(1)
