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
    # 步骤 1: 点击启动象盒找房App (坐标点击)
    driver.tap([(668, 824)])
    time.sleep(1)

    # 步骤 2: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 3: 点击首页金刚区的'二手房'入口 (坐标点击)
    driver.tap([(335, 458)])
    time.sleep(1)

    # 步骤 4: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 5: 点击左上角返回按钮回到二手房列表页 (坐标点击)
    driver.tap([(81, 165)])
    time.sleep(1)

    # 步骤 6: 点击'区域'筛选项以展开区域选择面板 (坐标点击)
    driver.tap([(118, 297)])
    time.sleep(1)

    # 步骤 7: 在区域筛选列表中选择'岳麓区' (坐标点击)
    driver.tap([(306, 845)])
    time.sleep(1)

    # 步骤 8: 点击确定按钮应用'岳麓区'筛选条件 (坐标点击)
    driver.tap([(744, 1595)])
    time.sleep(1)

    # 步骤 9: 点击'排序'展开排序选项菜单 (坐标点击)
    driver.tap([(912, 579)])
    time.sleep(1)

    # 步骤 10: 选择'总价从低到高'排序选项 (坐标点击)
    driver.tap([(147, 552)])
    time.sleep(1)
