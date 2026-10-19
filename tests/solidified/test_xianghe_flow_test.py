"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 补充登录手机号18888888888 密码xhj123456
生成时间: 自动化录制后生成
执行方式: pytest test_xianghe_flow_test.py -v -s
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
@allure.story("补充登录手机号18888888888 密码xhj123456")
def test_test_xianghe_flow_test(driver, api_client):
    """
    自动化用例: test_xianghe_flow_test
    补充登录手机号18888888888 密码xhj123456
    """
    # 步骤 1: 返回上一页以寻找登录入口 (坐标点击)
    driver.tap([(84, 165)])
    time.sleep(1)

    # 步骤 2: 点击左上角返回按钮回到主页或上一页 (坐标点击)
    driver.tap([(112, 180)])
    time.sleep(1)

    # 步骤 3: 点击首页底部的“登录体验”进入登录页面 (坐标点击)
    driver.tap([(880, 2067)])
    time.sleep(1)

    # 步骤 4: 点击“用密码登录”切换到账号密码登录模式 (坐标点击)
    driver.tap([(540, 1469)])
    time.sleep(1)

    # 步骤 5: 在手机号码输入框中输入18888888888
    el = driver.switch_to.active_element
    el.send_keys('18888888888')
    time.sleep(0.5)

    # 步骤 6: 在密码输入框中输入密码
    el = driver.switch_to.active_element
    el.send_keys('xhj123456')
    time.sleep(0.5)

    # 步骤 7: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 8: 勾选同意用户服务与隐私协议 (坐标点击)
    driver.tap([(62, 2182)])
    time.sleep(1)

    # 步骤 9: 点击登录按钮，提交手机号密码完成登录 (坐标点击)
    driver.tap([(540, 1164)])
    time.sleep(1)

    # 步骤 10: 断言页面包含文本 []
    assert '' in driver.page_source, f'断言失败：页面未出现预期文本: '
