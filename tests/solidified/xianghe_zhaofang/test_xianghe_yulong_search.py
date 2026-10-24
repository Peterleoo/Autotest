"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 进入象盒找房首页，点击顶部搜索栏，输入或点击热门小区'钰龙天下'，触发搜索进入房源列表，滑动查看并断言房源结果
生成时间: 自动化录制后生成
执行方式: pytest test_xianghe_yulong_search.py -v -s
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
@allure.story("进入象盒找房首页，点击顶部搜索栏，输入或点击热门小区'钰龙天下'，触发搜索进入房源列表，滑动查看并断言房源结果")
def test_test_xianghe_yulong_search(driver, api_client):
    """
    自动化用例: test_xianghe_yulong_search
    进入象盒找房首页，点击顶部搜索栏，输入或点击热门小区'钰龙天下'，触发搜索进入房源列表，滑动查看并断言房源结果
    """
    # 步骤 1: 点击顶部搜索框进入搜索输入及热门搜索界面 (坐标点击)
    driver.tap([(483, 165)])
    time.sleep(1)

    # 步骤 2: 在搜索框输入目标小区名称'钰龙天下'
    el = driver.switch_to.active_element
    el.send_keys('钰龙天下')
    time.sleep(0.5)

    # 步骤 3: 点击软键盘搜索按钮触发房源搜索 (坐标点击)
    driver.tap([(984, 2166)])
    time.sleep(1)

    # 步骤 4: 滑动手势 [up]
    # 自适应窗口滚动
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 600)
    time.sleep(1)

    # 步骤 5: 断言页面包含文本 [钰龙天下]
    assert '钰龙天下' in driver.page_source, f'断言失败：页面未出现预期文本: 钰龙天下'
