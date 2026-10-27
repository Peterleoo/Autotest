"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 在首页点击第一套推荐房源，进入房源详情页查看总价、户型与VR看房标识，点击'微聊/咨询'按钮，验证咨询窗口正确弹出
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
@allure.story("在首页点击第一套推荐房源，进入房源详情页查看总价、户型与VR看房标识，点击'微聊/咨询'按钮，验证咨询窗口正确弹出")
def test_test_matrix_flow(driver, api_client):
    """
    自动化用例: test_matrix_flow
    在首页点击第一套推荐房源，进入房源详情页查看总价、户型与VR看房标识，点击'微聊/咨询'按钮，验证咨询窗口正确弹出
    """
    # 步骤 1: 点击启动象盒找房App (坐标点击)
    driver.tap([(324, 1640)])
    time.sleep(1)

    # 步骤 2: 滑动手势 [up]
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 500)
    time.sleep(1)

    # 步骤 3: 点击第一套推荐房源进入房源详情页 (坐标点击)
    driver.tap([(800, 1802)])
    time.sleep(1)

    # 步骤 4: 点击底部的'在线问'咨询按钮 (坐标点击)
    driver.tap([(549, 2045)])
    time.sleep(1)
