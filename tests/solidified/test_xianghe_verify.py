"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 打开象盒找房，验证主界面正常显示
生成时间: 自动化录制后生成
执行方式: pytest test_xianghe_verify.py -v -s
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
@allure.story("打开象盒找房，验证主界面正常显示")
def test_test_xianghe_verify(driver, api_client):
    """
    自动化用例: test_xianghe_verify
    打开象盒找房，验证主界面正常显示
    """
    # 步骤 1: 断言页面包含文本 [二手房]
    assert '二手房' in driver.page_source, f'断言失败：页面未出现预期文本: 二手房'

    # 步骤 2: 断言页面包含文本 [首页]
    assert '首页' in driver.page_source, f'断言失败：页面未出现预期文本: 首页'

    # 步骤 3: 断言页面包含文本 [请输入小区名或地址搜索]
    assert '请输入小区名或地址搜索' in driver.page_source, f'断言失败：页面未出现预期文本: 请输入小区名或地址搜索'
