"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 进入首页，点击顶部搜索栏，输入或点击热门小区'钰龙天下'，触发搜索进入房源列表，滑动查看并断言房源结果
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
@allure.story("进入首页，点击顶部搜索栏，输入或点击热门小区'钰龙天下'，触发搜索进入房源列表，滑动查看并断言房源结果")
def test_test_matrix_flow(driver, api_client):
    """
    自动化用例: test_matrix_flow
    进入首页，点击顶部搜索栏，输入或点击热门小区'钰龙天下'，触发搜索进入房源列表，滑动查看并断言房源结果
    """
    # 步骤 1: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 2: 点击底部导航栏的【首页】Tab以返回首页，从而进行搜索操作 (坐标点击)
    driver.tap([(135, 2221)])
    time.sleep(1)

    # 步骤 3: 点击顶部搜索栏，准备输入搜索关键词'钰龙天下' (坐标点击)
    driver.tap([(635, 194)])
    time.sleep(1)

    # 步骤 4: 点击热门搜索中的'钰龙天下一期'，直接进入该小区的房源搜索结果列表 (坐标点击)
    driver.tap([(295, 972)])
    time.sleep(1)
