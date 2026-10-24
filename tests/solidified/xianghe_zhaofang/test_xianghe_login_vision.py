"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: 测试登录流程，勾选同意用户协议，输入测试手机号并验证鉴权
生成时间: 自动化录制后生成
执行方式: pytest test_xianghe_login_vision.py -v -s
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
@allure.story("测试登录流程，勾选同意用户协议，输入测试手机号并验证鉴权")
def test_test_xianghe_login_vision(driver, api_client):
    """
    自动化用例: test_xianghe_login_vision
    测试登录流程，勾选同意用户协议，输入测试手机号并验证鉴权
    """
    # 步骤 1: 定位手机号输入框，准备输入测试手机号码 (坐标点击)
    driver.tap([(540, 750)])
    time.sleep(1)

    # 步骤 2: 在手机号输入框中输入测试手机号，继续登录流程
    el = driver.switch_to.active_element
    el.send_keys('13800138000')
    time.sleep(0.5)

    # 步骤 3: 勾选同意《象盒隐私政策》及《象盒用户服务协议》等协议
    driver.find_element(AppiumBy.ACCESSIBILITY_ID, '勾选同意').click()
    time.sleep(1)

    # 步骤 4: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 5: 点击获取验证码，触发短信验证码发送以继续登录鉴权流程
    driver.find_element(AppiumBy.ACCESSIBILITY_ID, '获取验证码').click()
    time.sleep(1)

    # 步骤 6: 勾选同意隐私政策、用户服务协议等协议，满足登录前置条件
    driver.find_element(AppiumBy.ACCESSIBILITY_ID, '勾选同意').click()
    time.sleep(1)

    # 步骤 7: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 8: 协议已勾选，重新点击“获取验证码”按钮触发验证码短信发送
    driver.find_element(AppiumBy.ACCESSIBILITY_ID, '获取验证码').click()
    time.sleep(1)

    # 步骤 9: 在验证码输入框中输入测试验证码，继续登录鉴权流程
    el = driver.switch_to.active_element
    el.send_keys('123456')
    time.sleep(0.5)

    # 步骤 10: 提交手机号与验证码，执行登录注册并验证鉴权结果
    driver.find_element(AppiumBy.ACCESSIBILITY_ID, '登录/注册').click()
    time.sleep(1)

    # 步骤 11: 手机号和验证码已输入，需先勾选同意《象盒隐私政策》等协议，才能激活登录按钮 (坐标点击)
    driver.tap([(62, 2182)])
    time.sleep(1)

    # 步骤 12: 模拟返回键
    driver.back()
    time.sleep(1)

    # 步骤 13: 勾选同意《象盒隐私政策》等协议以激活登录按钮 (坐标点击)
    driver.tap([(62, 2182)])
    time.sleep(1)

    # 步骤 14: 提交手机号与验证码执行登录，验证鉴权结果
    driver.find_element(AppiumBy.ACCESSIBILITY_ID, '登录/注册').click()
    time.sleep(1)

    # 步骤 15: 点击登录/注册按钮，提交手机号与验证码进行登录鉴权验证
    driver.find_element(AppiumBy.ACCESSIBILITY_ID, '登录/注册').click()
    time.sleep(1)
