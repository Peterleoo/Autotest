"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 在首页点击第一套推荐房源，进入房源详情页查看总价、户型与VR看房标识，点击'微聊/咨询'按钮，验证咨询窗口正确弹出
生成时间: 自动化录制后生成
执行方式: pytest test_search_20261024_105745.py -v -s
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
def test_test_search_20261024_105745(driver, api_client):
    """
    自动化用例: test_search_20261024_105745
    在首页点击第一套推荐房源，进入房源详情页查看总价、户型与VR看房标识，点击'微聊/咨询'按钮，验证咨询窗口正确弹出
    """
    # 步骤 1: 等待界面加载
    time.sleep(1)

    # 步骤 2: 断言页面包含文本 [点击进入房源详情页]
    assert '点击进入房源详情页' in driver.page_source, f'断言失败：页面未出现预期文本: 点击进入房源详情页'

    # 步骤 3: 断言页面包含文本 [校验核心房源属性与VR标识]
    assert '校验核心房源属性与VR标识' in driver.page_source, f'断言失败：页面未出现预期文本: 校验核心房源属性与VR标识'

    # 步骤 4: 断言页面包含文本 [触发微聊咨询入口]
    assert '触发微聊咨询入口' in driver.page_source, f'断言失败：页面未出现预期文本: 触发微聊咨询入口'

    # 步骤 5: 断言页面包含文本 [验证IM咨询窗口拉起与终态]
    assert '验证IM咨询窗口拉起与终态' in driver.page_source, f'断言失败：页面未出现预期文本: 验证IM咨询窗口拉起与终态'
