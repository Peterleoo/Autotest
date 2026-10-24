"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 打开应用，若有隐私政策点击同意，进入登录界面输入账号密码，测试登录跳转并断言鉴权接口返回 200
生成时间: 自动化录制后生成
执行方式: pytest test_auth_20261022_100053.py -v -s
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
@allure.story("打开应用，若有隐私政策点击同意，进入登录界面输入账号密码，测试登录跳转并断言鉴权接口返回 200")
def test_test_auth_20261022_100053(driver, api_client):
    """
    自动化用例: test_auth_20261022_100053
    打开应用，若有隐私政策点击同意，进入登录界面输入账号密码，测试登录跳转并断言鉴权接口返回 200
    """
    # 步骤 1: 等待界面加载
    time.sleep(1)

    # 步骤 2: 断言页面包含文本 [进入并就绪登录页面]
    assert '进入并就绪登录页面' in driver.page_source, f'断言失败：页面未出现预期文本: 进入并就绪登录页面'

    # 步骤 3: 断言页面包含文本 [输入账号密码并提交登录]
    assert '输入账号密码并提交登录' in driver.page_source, f'断言失败：页面未出现预期文本: 输入账号密码并提交登录'

    # 步骤 4: 断言页面包含文本 [拦截并断言鉴权接口状态码]
    assert '拦截并断言鉴权接口状态码' in driver.page_source, f'断言失败：页面未出现预期文本: 拦截并断言鉴权接口状态码'

    # 步骤 5: 断言页面包含文本 [断言登录成功页面跳转]
    assert '断言登录成功页面跳转' in driver.page_source, f'断言失败：页面未出现预期文本: 断言登录成功页面跳转'

    # 步骤 6: 断言页面包含文本 [执行追加意图：继续]
    assert '执行追加意图：继续' in driver.page_source, f'断言失败：页面未出现预期文本: 执行追加意图：继续'

    # 步骤 7: 断言页面包含文本 [追随指令: 继续]
    assert '追随指令: 继续' in driver.page_source, f'断言失败：页面未出现预期文本: 追随指令: 继续'
