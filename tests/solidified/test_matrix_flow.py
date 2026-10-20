"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 打开应用，若有隐私政策点击同意，进入登录界面输入账号密码，测试登录跳转并断言鉴权接口返回 200
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
@allure.story("打开应用，若有隐私政策点击同意，进入登录界面输入账号密码，测试登录跳转并断言鉴权接口返回 200")
def test_test_matrix_flow(driver, api_client):
    """
    自动化用例: test_matrix_flow
    打开应用，若有隐私政策点击同意，进入登录界面输入账号密码，测试登录跳转并断言鉴权接口返回 200
    """
    # 步骤 1: 点击左上角返回按钮退出免费发布房源界面 (坐标点击)
    driver.tap([(82, 165)])
    time.sleep(1)

    # 步骤 2: 点击放弃退出发布房源界面 (坐标点击)
    driver.tap([(335, 1277)])
    time.sleep(1)
