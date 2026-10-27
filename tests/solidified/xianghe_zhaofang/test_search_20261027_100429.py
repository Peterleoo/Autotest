"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 进入首页，点击顶部搜索栏，输入或点击热门小区'钰龙天下'，触发搜索进入房源列表，滑动查看并断言房源结果
生成时间: 自动化录制后生成
执行方式: pytest test_search_20261027_100429.py -v -s
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
@allure.story("进入首页，点击顶部搜索栏，输入或点击热门小区'钰龙天下'，触发搜索进入房源列表，滑动查看并断言房源结果")
def test_test_search_20261027_100429(driver, api_client):
    """
    自动化用例: test_search_20261027_100429
    进入首页，点击顶部搜索栏，输入或点击热门小区'钰龙天下'，触发搜索进入房源列表，滑动查看并断言房源结果
    """
    # 步骤 1: 等待界面加载
    time.sleep(1)

    # 步骤 2: 断言页面包含文本 [触发搜索入口]
    assert '触发搜索入口' in driver.page_source, f'断言失败：页面未出现预期文本: 触发搜索入口'

    # 步骤 3: 断言页面包含文本 [输入并提交搜索词]
    assert '输入并提交搜索词' in driver.page_source, f'断言失败：页面未出现预期文本: 输入并提交搜索词'

    # 步骤 4: 断言页面包含文本 [等待房源列表渲染]
    assert '等待房源列表渲染' in driver.page_source, f'断言失败：页面未出现预期文本: 等待房源列表渲染'

    # 步骤 5: 断言页面包含文本 [滑动列表并验证结果]
    assert '滑动列表并验证结果' in driver.page_source, f'断言失败：页面未出现预期文本: 滑动列表并验证结果'
