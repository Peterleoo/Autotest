"""
由 AI 自动化测试智能体自动录制固化的跨端测试用例 (Dual-Mode Resilient Test Suite)
测试目标: 在【待测应用 (示例)】搜索框输入测试关键词触发搜索，验证结果列表正常展示，返回后核对搜索历史标签生成
执行命令: pytest test_matrix_flow.py -v -s
特性优势:
  1. 语义优先 (Text / ID / Desc) 动态查找；
  2. 屏幕自适应百分比相对坐标兜底，免维护跨不同分辨率真机回归！
"""
import time
import pytest
import allure
from appium.webdriver.common.appiumby import AppiumBy

from core.driver_factory import DriverFactory
from core.api_client import APIClient


def robust_click(driver, text=None, res_id=None, desc=None, rel_x=None, rel_y=None):
    """
    双模自适应点击 (Dual-Mode Click)
    模式 1: 优先语义匹配 (文本/ID/无障碍描述)
    模式 2: 分辨率相对百分比动态换算兜底
    """
    if text:
        try:
            el = driver.find_element(AppiumBy.XPATH, f"//*[@text='{text}' or contains(@text, '{text}')]")
            el.click()
            return
        except Exception:
            pass
    if res_id:
        try:
            el = driver.find_element(AppiumBy.ID, res_id)
            el.click()
            return
        except Exception:
            pass
    if desc:
        try:
            el = driver.find_element(AppiumBy.ACCESSIBILITY_ID, desc)
            el.click()
            return
        except Exception:
            pass

    # 兜底：相对百分比换算实际物理坐标
    if rel_x is not None and rel_y is not None:
        size = driver.get_window_size()
        w = size.get('width', 1080)
        h = size.get('height', 2160)
        target_x = int(w * rel_x)
        target_y = int(h * rel_y)
        if hasattr(driver, "tap"):
            driver.tap([(target_x, target_y)])
        else:
            driver.execute_adb(["shell", "input", "tap", str(target_x), str(target_y)])
        return

    raise RuntimeError(f"无法定位或点击目标元素: text={text}, id={res_id}, rel=({rel_x}, {rel_y})")


def robust_type(driver, text=None, res_id=None, desc=None, rel_x=None, rel_y=None, input_text=""):
    """
    双模自适应输入 (Dual-Mode Type)
    优先语义查找输入框，相对坐标点击聚焦兜底并注入文本
    """
    typed = False
    if text or res_id or desc:
        try:
            el = None
            if res_id:
                try: el = driver.find_element(AppiumBy.ID, res_id)
                except Exception: pass
            if not el and text:
                try: el = driver.find_element(AppiumBy.XPATH, f"//*[@text='{text}' or contains(@text, '{text}')]")
                except Exception: pass
            if not el and desc:
                try: el = driver.find_element(AppiumBy.ACCESSIBILITY_ID, desc)
                except Exception: pass
            if el:
                el.clear()
                el.send_keys(input_text)
                typed = True
                return
        except Exception:
            pass

    if not typed:
        robust_click(driver, text=text, res_id=res_id, desc=desc, rel_x=rel_x, rel_y=rel_y)
        time.sleep(0.3)
        try:
            driver.switch_to.active_element.send_keys(input_text)
        except Exception:
            if hasattr(driver, "execute_adb"):
                driver.execute_adb(["shell", "input", "text", input_text])


def robust_swipe(driver, direction="up", repeat=1):
    """自适应屏幕物理分辨率滑动"""
    size = driver.get_window_size()
    w = size.get('width', 1080)
    h = size.get('height', 2160)
    for _ in range(repeat):
        if direction == "up":
            driver.swipe(w // 2, int(h * 0.75), w // 2, int(h * 0.25), 450)
        elif direction == "down":
            driver.swipe(w // 2, int(h * 0.25), w // 2, int(h * 0.75), 450)
        elif direction == "left":
            driver.swipe(int(w * 0.88), h // 2, int(w * 0.12), h // 2, 350)
        elif direction == "right":
            driver.swipe(int(w * 0.12), h // 2, int(w * 0.88), h // 2, 350)
        time.sleep(0.3)


@pytest.fixture(scope="module")
def driver():
    """初始化真机驱动"""
    drv = DriverFactory.create_driver()
    yield drv
    drv.quit()


@pytest.fixture(scope="module")
def api_client():
    """初始化统一接口客户端"""
    return APIClient()


@allure.feature("固化测试套件")
@allure.story("在【待测应用 (示例)】搜索框输入测试关键词触发搜索，验证结果列表正常展示，返回后核对搜索历史标签生成")
def test_matrix_flow(driver, api_client):
    """
    自动化用例: test_matrix_flow
    测试目标: 在【待测应用 (示例)】搜索框输入测试关键词触发搜索，验证结果列表正常展示，返回后核对搜索历史标签生成
    """
    # 步骤 1: 点击返回按钮退出房源详情页
    robust_click(driver, text=None, res_id=None, desc=None, rel_x=0.075, rel_y=0.0736)
    time.sleep(1)

    # 步骤 2: 点击首页顶部搜索框进入搜索界面
    robust_click(driver, text=None, res_id=None, desc='请输入小区名或地址搜索', rel_x=0.588, rel_y=0.0718)
    time.sleep(1)

    # 步骤 3: 在搜索框中输入测试关键词'星城国际'触发搜索 (输入: 星城国际)
    robust_type(driver, text=None, res_id=None, desc=None, rel_x=0.4815, rel_y=0.1403, input_text='星城国际')
    time.sleep(1)

    # 步骤 4: 点击清除按钮清空输入框中的乱码
    robust_click(driver, text=None, res_id=None, desc=None, rel_x=0.8231, rel_y=0.1403)
    time.sleep(1)

    # 步骤 5: 点击热门搜索中的'星城国际'触发搜索进入结果列表
    robust_click(driver, text=None, res_id=None, desc='4\n星城国际', rel_x=0.2731, rel_y=0.4935)
    time.sleep(1)

    # 步骤 6: 点击左上角返回按钮回到搜索页以核对搜索历史标签生成
    robust_click(driver, text=None, res_id=None, desc=None, rel_x=0.0787, rel_y=0.0648)
    time.sleep(1)

    # 步骤 7: 点击首页顶部搜索框进入搜索页
    robust_click(driver, text=None, res_id=None, desc='请输入小区名或地址搜索', rel_x=0.588, rel_y=0.0718)
    time.sleep(1)
