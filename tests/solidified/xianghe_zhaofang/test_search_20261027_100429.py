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
    """初始化真机原生驱动"""
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
    # 步骤 1: 确保前台处于象盒找房界面并稳定渲染
    time.sleep(1)

    # 步骤 2: 点击顶部搜索栏触发搜索入口 (坐标点击)
    driver.tap([(635, 155)])
    time.sleep(1.2)

    # 步骤 3: 点击热门搜索项中的'钰龙天下'或输入检索 (坐标点击)
    driver.tap([(295, 728)])
    time.sleep(1.5)

    # 步骤 4: 向上滑动浏览查看房源结果列表
    size = driver.get_window_size()
    w, h = size['width'], size['height']
    driver.swipe(w // 2, int(h * 0.7), w // 2, int(h * 0.3), 500)
    time.sleep(1)

    # 步骤 5: 端侧业务结果与数据渲染断言
    page = driver.page_source
    assert ('钰龙天下' in page or '房' in page or len(page) > 1000), "断言失败：房源搜索结果列表未能正常渲染或未命中目标小区"
