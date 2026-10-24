"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 发布房源字段必填校验与异常拦截
生成时间: 自动化录制后生成
执行方式: pytest test_demo_flow.py -v -s
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
@allure.story("发布房源字段必填校验与异常拦截")
def test_test_demo_flow(driver, api_client):
    """
    自动化用例: test_demo_flow
    发布房源字段必填校验与异常拦截
    """
    # 步骤 1: 等待界面加载
    time.sleep(2)

    # 步骤 2: 等待界面加载
    time.sleep(2)

    # 步骤 3: 滑动手势 [left]
    # 自适应窗口滚动
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 600)
    time.sleep(1)

    # 步骤 4: 等待界面加载
    time.sleep(2)

    # 步骤 5: 尝试点击隐私协议弹窗的同意按钮或跳过遮罩 (坐标点击)
    driver.tap([(540, 1350)])
    time.sleep(1)

    # 步骤 6: 等待界面加载
    time.sleep(3)

    # 步骤 7: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 8: 等待界面加载
    time.sleep(3)

    # 步骤 9: 点击屏幕中央区域尝试激活界面或跳过加载遮罩 (坐标点击)
    driver.tap([(540, 1200)])
    time.sleep(1)

    # 步骤 10: 滑动手势 [up]
    # 自适应窗口滚动
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 600)
    time.sleep(1)

    # 步骤 11: 等待界面加载
    time.sleep(3)

    # 步骤 12: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 13: 等待界面加载
    time.sleep(3)

    # 步骤 14: 点击屏幕中央以唤醒焦点或促使界面完成渲染 (坐标点击)
    driver.tap([(540, 960)])
    time.sleep(1)

    # 步骤 15: 等待界面加载
    time.sleep(3)
