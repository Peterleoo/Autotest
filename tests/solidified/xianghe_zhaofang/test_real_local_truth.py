"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 象盒找房真实本地自测回归
生成时间: 自动化录制后生成
执行方式: pytest test_real_local_truth.py -v -s
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
@allure.story("象盒找房真实本地自测回归")
def test_test_real_local_truth(driver, api_client):
    """
    自动化用例: test_real_local_truth
    象盒找房真实本地自测回归
    """
    # 步骤 1: 同意隐私政策协议弹窗
    driver.find_element(AppiumBy.XPATH, "//*[@text='同意' or contains(@resource-id, 'agree')]").click()
    time.sleep(1)

    # 步骤 2: 定位并输入测试手机号
    el = driver.find_element(AppiumBy.XPATH, "//*[@text='请输入手机号' or contains(@resource-id, 'phone')]")
    el.clear()
    el.send_keys('13800138000')
    time.sleep(0.5)

    # 步骤 3: 接口测试 [GET /api/config]
    resp = api_client.request('GET', '/api/config')
    assert resp.status_code == 200, f'接口状态码断言失败: {resp.status_code} != 200'

    # 步骤 4: 点击获取验证码/登录交互
    driver.find_element(AppiumBy.XPATH, "//*[@text='获取验证码' or contains(@resource-id, 'btn_login')]").click()
    time.sleep(1)

    # 步骤 5: 断言页面包含文本 [象盒找房]
    assert '象盒找房' in driver.page_source, f'断言失败：页面未出现预期文本: 象盒找房'
