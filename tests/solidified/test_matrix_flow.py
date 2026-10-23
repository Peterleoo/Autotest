"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 这里的小区明显要选择啊 侧哪里去了？
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
@allure.story("这里的小区明显要选择啊 侧哪里去了？")
def test_test_matrix_flow(driver, api_client):
    """
    自动化用例: test_matrix_flow
    这里的小区明显要选择啊 侧哪里去了？
    """
    # 步骤 1: 点击顶部‘请输入小区名或地名’搜索框，进入小区选择与搜索页面 (坐标点击)
    driver.tap([(438, 152)])
    time.sleep(1)

    # 步骤 2: 在搜索框输入小区关键字以展示小区联想选择列表
    el = driver.switch_to.active_element
    el.send_keys('万达')
    time.sleep(0.5)

    # 步骤 3: 在搜索框重新输入有效的小区关键词以唤起小区联想列表供选择
    el = driver.switch_to.active_element
    el.send_keys('保利')
    time.sleep(0.5)

    # 步骤 4: 点击桌面上的‘象盒找房’应用图标重新进入应用 (坐标点击)
    driver.tap([(668, 824)])
    time.sleep(1)

    # 步骤 5: 在搜索框输入小区关键字以展示小区选择列表
    el = driver.switch_to.active_element
    el.send_keys('万达')
    time.sleep(0.5)

    # 步骤 6: 在搜索框输入真实小区名称‘万达’以唤起小区联想选择列表
    el = driver.switch_to.active_element
    el.send_keys('万达')
    time.sleep(0.5)

    # 步骤 7: 清空搜索框中的无效字符以展示小区列表 (坐标点击)
    driver.tap([(889, 309)])
    time.sleep(1)

    # 步骤 8: 在搜索框输入小区关键字以唤起小区联想列表供选择
    el = driver.switch_to.active_element
    el.send_keys('万科')
    time.sleep(0.5)

    # 步骤 9: 点击清空按钮清除搜索框中的乱码字符 (坐标点击)
    driver.tap([(889, 309)])
    time.sleep(1)

    # 步骤 10: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 11: 在搜索框输入小区关键词触发联想列表展示
    el = driver.switch_to.active_element
    el.send_keys('万科')
    time.sleep(0.5)

    # 步骤 12: 清空搜索框内的无效乱码字符 (坐标点击)
    driver.tap([(889, 309)])
    time.sleep(1)

    # 步骤 13: 在搜索框输入小区名称以呼出小区候选列表供选择
    el = driver.switch_to.active_element
    el.send_keys('保利')
    time.sleep(0.5)

    # 步骤 14: 点击搜索框内的清空按钮清除无效内容 (坐标点击)
    driver.tap([(889, 309)])
    time.sleep(1)

    # 步骤 15: 在搜索框输入小区名称‘万达’以调出小区候选列表
    el = driver.switch_to.active_element
    el.send_keys('万达')
    time.sleep(0.5)
