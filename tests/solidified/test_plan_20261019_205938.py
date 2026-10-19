"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 象盒找房用户登录与房源核心链路全链路测试
生成时间: 自动化录制后生成
执行方式: pytest test_plan_20261019_205938.py -v -s
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
@allure.story("象盒找房用户登录与房源核心链路全链路测试")
def test_test_plan_20261019_205938(driver, api_client):
    """
    自动化用例: test_plan_20261019_205938
    象盒找房用户登录与房源核心链路全链路测试
    """
    pass
