"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 进入象盒找房应用，同意隐私政策协议，进入首页浏览推荐房源
生成时间: 自动化录制后生成
执行方式: pytest test_real_phone_browse_flow.py -v -s
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
@allure.story("进入象盒找房应用，同意隐私政策协议，进入首页浏览推荐房源")
def test_test_real_phone_browse_flow(driver, api_client):
    """
    自动化用例: test_real_phone_browse_flow
    进入象盒找房应用，同意隐私政策协议，进入首页浏览推荐房源
    """
    # 步骤 1: 点击‘马上体验’按钮进入应用 (坐标点击)
    driver.tap([(540, 1602)])
    time.sleep(1)

    # 步骤 2: 点击‘随便看看’快速进入应用首页 (坐标点击)
    driver.tap([(540, 1613)])
    time.sleep(1)

    # 步骤 3: 等待界面加载
    time.sleep(3)

    # 步骤 4: 点击‘同意使用’关闭摇一摇反馈弹窗 (坐标点击)
    driver.tap([(710, 1393)])
    time.sleep(1)

    # 步骤 5: 滑动手势 [up]
    # 自适应窗口滚动
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 600)
    time.sleep(1)
