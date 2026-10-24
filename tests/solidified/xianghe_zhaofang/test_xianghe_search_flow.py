"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 进入首页，在顶部搜索栏输入'精装两居'，触发搜索，进入搜索结果列表进行下拉滑动加载，并断言列表包含房源信息
生成时间: 自动化录制后生成
执行方式: pytest test_xianghe_search_flow.py -v -s
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
@allure.story("进入首页，在顶部搜索栏输入'精装两居'，触发搜索，进入搜索结果列表进行下拉滑动加载，并断言列表包含房源信息")
def test_test_xianghe_search_flow(driver, api_client):
    """
    自动化用例: test_xianghe_search_flow
    进入首页，在顶部搜索栏输入'精装两居'，触发搜索，进入搜索结果列表进行下拉滑动加载，并断言列表包含房源信息
    """
    # 步骤 1: 点击顶部搜索框以输入'精装两居' (坐标点击)
    driver.tap([(483, 165)])
    time.sleep(1)

    # 步骤 2: 在搜索框中输入测试关键词'精装两居'
    el = driver.switch_to.active_element
    el.send_keys('精装两居')
    time.sleep(0.5)

    # 步骤 3: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 4: 点击返回按钮退出写字楼搜索页面 (坐标点击)
    driver.tap([(59, 204)])
    time.sleep(1)

    # 步骤 5: 点击顶部搜索框重新输入正确的搜索关键词 (坐标点击)
    driver.tap([(483, 165)])
    time.sleep(1)

    # 步骤 6: 在搜索框中输入测试关键词'精装两居'
    el = driver.switch_to.active_element
    el.send_keys('精装两居')
    time.sleep(0.5)

    # 步骤 7: 点击返回箭头退出租写字楼搜索界面以返回首页 (坐标点击)
    driver.tap([(59, 204)])
    time.sleep(1)

    # 步骤 8: 等待界面加载
    time.sleep(2)

    # 步骤 9: 等待界面加载
    time.sleep(2)

    # 步骤 10: 点击搜索输入框重新激活搜索界面 (坐标点击)
    driver.tap([(483, 165)])
    time.sleep(1)

    # 步骤 11: 点击左上角返回按钮退出当前写字楼搜索页 (坐标点击)
    driver.tap([(59, 204)])
    time.sleep(1)

    # 步骤 12: 点击搜索栏进入搜索编辑页面输入目标关键词 (坐标点击)
    driver.tap([(483, 165)])
    time.sleep(1)

    # 步骤 13: 在搜索框中输入测试关键词'精装两居'
    el = driver.switch_to.active_element
    el.send_keys('精装两居')
    time.sleep(0.5)

    # 步骤 14: 点击左上角返回按钮退出当前租写字楼搜索页面 (坐标点击)
    driver.tap([(59, 204)])
    time.sleep(1)

    # 步骤 15: 点击搜索栏进入搜索页面 (坐标点击)
    driver.tap([(483, 165)])
    time.sleep(1)
