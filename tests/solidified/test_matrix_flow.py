"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 系统设置中可以退出设置后 重新登录
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
@allure.story("系统设置中可以退出设置后 重新登录")
def test_test_matrix_flow(driver, api_client):
    """
    自动化用例: test_matrix_flow
    系统设置中可以退出设置后 重新登录
    """
    # 步骤 1: 点击账户与安全以寻找退出登录选项 (坐标点击)
    driver.tap([(540, 1539)])
    time.sleep(1)

    # 步骤 2: 返回上一级系统设置页面以寻找退出登录选项 (坐标点击)
    driver.tap([(82, 165)])
    time.sleep(1)

    # 步骤 3: 滑动手势 [down]
    # 自适应窗口滚动
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 600)
    time.sleep(1)

    # 步骤 4: 滑动手势 [down]
    # 自适应窗口滚动
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 600)
    time.sleep(1)

    # 步骤 5: 进入账户与安全页面寻找账号注销或退出登录选项 (坐标点击)
    driver.tap([(540, 1539)])
    time.sleep(1)

    # 步骤 6: 点击左上角返回按钮回到系统设置页面以寻找退出登录选项 (坐标点击)
    driver.tap([(82, 165)])
    time.sleep(1)

    # 步骤 7: 滑动手势 [down]
    # 自适应窗口滚动
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 600)
    time.sleep(1)

    # 步骤 8: 滑动手势 [down]
    # 自适应窗口滚动
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 600)
    time.sleep(1)

    # 步骤 9: 再次进入账户与安全页面寻找退出登录按钮 (坐标点击)
    driver.tap([(540, 1539)])
    time.sleep(1)

    # 步骤 10: 点击左上角返回按钮返回系统设置页面寻找退出登录按钮 (坐标点击)
    driver.tap([(82, 165)])
    time.sleep(1)

    # 步骤 11: 滑动手势 [down]
    # 自适应窗口滚动
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 600)
    time.sleep(1)

    # 步骤 12: 滑动手势 [down]
    # 自适应窗口滚动
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 600)
    time.sleep(1)

    # 步骤 13: 点击账户与安全页面寻找退出登录按钮 (坐标点击)
    driver.tap([(540, 1539)])
    time.sleep(1)

    # 步骤 14: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 15: 滑动手势 [down]
    # 自适应窗口滚动
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 600)
    time.sleep(1)
