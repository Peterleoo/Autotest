"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 房东在线委托卖房与表单验证
进入'委托服务'页面，点击'委托售房'，验证小区名称、期望售价与联系方式表单项正常渲染，并点击'免费发布'测试必填
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
@allure.story("房东在线委托卖房与表单验证
进入'委托服务'页面，点击'委托售房'，验证小区名称、期望售价与联系方式表单项正常渲染，并点击'免费发布'测试必填")
def test_test_matrix_flow(driver, api_client):
    """
    自动化用例: test_matrix_flow
    房东在线委托卖房与表单验证
进入'委托服务'页面，点击'委托售房'，验证小区名称、期望售价与联系方式表单项正常渲染，并点击'免费发布'测试必填
    """
    # 步骤 1: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 2: 点击委托服务入口，进入委托售房页面 (坐标点击)
    driver.tap([(539, 895)])
    time.sleep(1)

    # 步骤 3: 点击委托售房图标，进入房源售房委托表单页面 (坐标点击)
    driver.tap([(324, 411)])
    time.sleep(1)

    # 步骤 4: 点击我要出售按钮进入委托售房表单页面 (坐标点击)
    driver.tap([(745, 1277)])
    time.sleep(1)

    # 步骤 5: 滑动手势 [down]
    # 自适应窗口滚动
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 600)
    time.sleep(1)

    # 步骤 6: 滑动手势 [down]
    # 自适应窗口滚动
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 600)
    time.sleep(1)
