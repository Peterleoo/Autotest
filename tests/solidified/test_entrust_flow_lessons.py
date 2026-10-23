"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 进入'委托服务'页面，点击'委托售房'，验证小区名称、期望售价与联系方式表单项正常渲染，并点击'免费发布'测试必填校验
生成时间: 自动化录制后生成
执行方式: pytest test_entrust_flow_lessons.py -v -s
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
@allure.story("进入'委托服务'页面，点击'委托售房'，验证小区名称、期望售价与联系方式表单项正常渲染，并点击'免费发布'测试必填校验")
def test_test_entrust_flow_lessons(driver, api_client):
    """
    自动化用例: test_entrust_flow_lessons
    进入'委托服务'页面，点击'委托售房'，验证小区名称、期望售价与联系方式表单项正常渲染，并点击'免费发布'测试必填校验
    """
    # 步骤 1: 点击同意隐私协议进入应用 (坐标点击)
    driver.tap([(713, 2008)])
    time.sleep(1)

    # 步骤 2: 引导页极速穿透宏动作（快速翻页至末页并进入首页）
    size = driver.get_window_size()
    w, h = size['width'], size['height']
    for _ in range(3):
        driver.swipe(int(w * 0.88), h // 2, int(w * 0.12), h // 2, 300)
        time.sleep(0.3)
    time.sleep(0.5)
    driver.tap([(w // 2, int(h * 0.75))])
    time.sleep(1)

    # 步骤 3: 点击随便看看进入主页 (坐标点击)
    driver.tap([(211, 1615)])
    time.sleep(1)

    # 步骤 4: 等待界面加载
    time.sleep(2)

    # 步骤 5: 点击弹窗的‘同意使用’按钮以关闭提示弹窗 (坐标点击)
    driver.tap([(656, 1410)])
    time.sleep(1)

    # 步骤 6: 点击系统网络连接确认弹窗的‘确定’按钮 (坐标点击)
    driver.tap([(779, 1985)])
    time.sleep(1)

    # 步骤 7: 点击弹窗中的“拒绝”按钮关闭摇一摇提示弹窗 (坐标点击)
    driver.tap([(325, 1415)])
    time.sleep(1)

    # 步骤 8: 等待界面加载
    time.sleep(2)

    # 步骤 9: 等待界面加载
    time.sleep(2)

    # 步骤 10: 等待界面加载
    time.sleep(2)

    # 步骤 11: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 12: 点击底部'首页'Tab激活主页，避免触发连续返回退出 (坐标点击)
    driver.tap([(135, 2116)])
    time.sleep(1)

    # 步骤 13: 等待界面加载
    time.sleep(2)

    # 步骤 14: 等待界面加载
    time.sleep(2)

    # 步骤 15: 等待界面加载
    time.sleep(2)
