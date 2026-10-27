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
    # 步骤 1: 点击我同意以同意隐私政策进入应用首页 (坐标点击)
    driver.tap([(713, 2064)])
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

    # 步骤 3: 点击随便看看进入应用主页 (坐标点击)
    driver.tap([(540, 1609)])
    time.sleep(1)

    # 步骤 4: 点击顶部搜索框进入搜索页 (坐标点击)
    driver.tap([(635, 155)])
    time.sleep(1)

    # 步骤 5: 点击热门搜索中的'钰龙天下一期'进入房源列表 (坐标点击)
    driver.tap([(295, 728)])
    time.sleep(1)

    # 步骤 6: 点击拒绝关闭新功能弹窗 (坐标点击)
    driver.tap([(327, 1387)])
    time.sleep(1)

    # 步骤 7: 点击热门搜索第一项'钰龙天下一期'进入房源列表 (坐标点击)
    driver.tap([(295, 728)])
    time.sleep(1)

    # 步骤 8: 滑动手势 [up]
    size = driver.get_window_size()
    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 500)
    time.sleep(1)
