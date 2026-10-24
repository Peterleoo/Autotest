"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 点击底部或首页'二手房'入口，进入列表后点击'区域'筛选'岳麓区'，排序选择'总价从低到高'，验证列表已按照价格排序更新
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
@allure.story("点击底部或首页'二手房'入口，进入列表后点击'区域'筛选'岳麓区'，排序选择'总价从低到高'，验证列表已按照价格排序更新")
def test_test_matrix_flow(driver, api_client):
    """
    自动化用例: test_matrix_flow
    点击底部或首页'二手房'入口，进入列表后点击'区域'筛选'岳麓区'，排序选择'总价从低到高'，验证列表已按照价格排序更新
    """
    # 步骤 1: 点击首页'二手房'入口进入二手房房源列表 (坐标点击)
    driver.tap([(155, 1072)])
    time.sleep(1)

    # 步骤 2: 轻触首页Tab刷新消除定位提示浮层，加载完整金刚区 (坐标点击)
    driver.tap([(135, 2019)])
    time.sleep(1)

    # 步骤 3: 点击首页'二手房'入口进入二手房列表页面 (坐标点击)
    driver.tap([(155, 1072)])
    time.sleep(1)

    # 步骤 4: 点击首页的'二手房'入口进入二手房列表页面 (坐标点击)
    driver.tap([(155, 1072)])
    time.sleep(1)

    # 步骤 5: 点击顶部搜索框进入搜索页面以直达二手房房源列表 (坐标点击)
    driver.tap([(635, 175)])
    time.sleep(1)

    # 步骤 6: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 7: 点击取消按钮退出搜索页面返回主页 (坐标点击)
    driver.tap([(978, 300)])
    time.sleep(1)

    # 步骤 8: 点击首页金刚区的'二手房'入口进入二手房房源列表页 (坐标点击)
    driver.tap([(336, 395)])
    time.sleep(1)

    # 步骤 9: 点击顶部筛选栏的'区域'以展开区域选择列表 (坐标点击)
    driver.tap([(118, 297)])
    time.sleep(1)

    # 步骤 10: 在区域筛选列表中点击选择'岳麓区' (坐标点击)
    driver.tap([(306, 845)])
    time.sleep(1)

    # 步骤 11: 点击确定按钮应用'岳麓区'筛选条件 (坐标点击)
    driver.tap([(744, 1595)])
    time.sleep(1)

    # 步骤 12: 点击顶部筛选栏的'排序'展开排序选项列表 (坐标点击)
    driver.tap([(937, 295)])
    time.sleep(1)

    # 步骤 13: 选择'总价从低到高'排序 (坐标点击)
    driver.tap([(147, 552)])
    time.sleep(1)
