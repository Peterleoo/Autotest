# -*- coding: utf-8 -*-
"""真机中文输入：借助 Appium Settings 的 UnicodeIME，以 IMAP-UTF7 编码经 `adb shell input text` 上屏

设计约束：
1. 绝不静默降级为截断/拼音输入——输错关键词会让测试"通过"却测错了对象；不可用时明确报错并给出排查指引；
2. 输入前记录用户原输入法，输入后恢复，避免手机键盘被测试输入法长期占用；
3. 上屏后回读输入框内容核对，确保 AI 后续决策基于真实输入结果。
"""
import base64
import logging
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger("ChineseInput")

UNICODE_IME_PACKAGE = "io.appium.settings"
UNICODE_IME_ID = "io.appium.settings/.UnicodeIME"
IME_SWITCH_TIMEOUT = 3.0
IME_BIND_TIMEOUT = 2.0
RAW_RETYPE_ATTEMPTS = 1
INSTALL_TIMEOUT = 60

APK_CANDIDATES = [
    Path.home() / ".appium" / "node_modules" / "appium-uiautomator2-driver" / "node_modules"
    / "io.appium.settings" / "apks" / "settings_apk-debug.apk",
    Path.home() / ".appium" / "node_modules" / "io.appium.settings" / "apks" / "settings_apk-debug.apk",
]


class ChineseInputUnavailable(RuntimeError):
    """真机无法输入中文（UnicodeIME 未安装或无法激活）"""


class InputMismatch(RuntimeError):
    """上屏后输入框内容与期望文本不一致"""


def contains_non_ascii(text: str) -> bool:
    return any(ord(c) > 127 for c in text)


def encode_imap_utf7(s: str) -> str:
    """RFC 3501 修改版 UTF-7：UnicodeIME 会将其解码还原为原始 Unicode 文本"""
    def _chunk(c: str) -> str:
        b = c.encode("utf-16be")
        return base64.b64encode(b).decode("ascii").rstrip("=").replace("/", ",")

    res = []
    for part in re.split(r"([^\x20-\x7e]+)", s):
        if not part:
            continue
        if all(0x20 <= ord(ch) <= 0x7e for ch in part):
            res.append(part.replace("&", "&-"))
        else:
            res.append(f"&{_chunk(part)}-")
    return "".join(res)


def _out(res: Any) -> str:
    if res is None:
        return ""
    if isinstance(res, (bytes, str)):
        return res.decode("utf-8", "ignore") if isinstance(res, bytes) else res
    stdout = getattr(res, "stdout", "") or ""
    return stdout.decode("utf-8", "ignore") if isinstance(stdout, bytes) else str(stdout)


def _shell(driver: Any, args: List[str], timeout: int = 15) -> str:
    return _out(driver.execute_adb(["shell"] + args, timeout=timeout)).strip()


def _find_local_apk() -> Optional[Path]:
    return next((p for p in APK_CANDIDATES if p.exists()), None)


def ensure_unicode_ime_installed(driver: Any) -> None:
    """未安装时自动从本机 Appium 目录安装 Appium Settings（含 UnicodeIME）"""
    if UNICODE_IME_PACKAGE in _shell(driver, ["pm", "list", "packages", UNICODE_IME_PACKAGE]):
        return
    apk = _find_local_apk()
    if not apk:
        raise ChineseInputUnavailable(
            f"真机未安装中文输入组件 {UNICODE_IME_PACKAGE}，且本机未找到安装包。"
            f"请执行 `appium driver install uiautomator2` 后重试，或手动安装 settings_apk-debug.apk"
        )
    logger.info(f"真机未安装中文输入组件，正在从本机自动安装: {apk}")
    result = _out(driver.execute_adb(["install", "-r", "-g", str(apk)], timeout=INSTALL_TIMEOUT))
    if "Success" not in result:
        raise ChineseInputUnavailable(f"自动安装中文输入组件失败: {result.strip()[:200]}")


def _current_ime(driver: Any) -> str:
    return _shell(driver, ["settings", "get", "secure", "default_input_method"])


def _ime_bound_to_field(driver: Any) -> bool:
    """系统设置切换成功 ≠ 输入法已接管当前输入框；以 InputMethodManager 的绑定状态为准"""
    dump = _shell(driver, ["dumpsys", "input_method"])
    return any(f"mCurId={UNICODE_IME_ID}" in line and "mBoundToMethod=true" in line for line in dump.splitlines())


def _activate_unicode_ime(driver: Any) -> None:
    _shell(driver, ["ime", "enable", UNICODE_IME_ID])
    _shell(driver, ["ime", "set", UNICODE_IME_ID])
    deadline = time.time() + IME_SWITCH_TIMEOUT
    while _current_ime(driver) != UNICODE_IME_ID:
        if time.time() >= deadline:
            raise ChineseInputUnavailable("UnicodeIME 切换超时，系统未将其设为当前输入法（部分 ROM 需在设置中允许该输入法）")
        time.sleep(0.2)
    # 等待输入法真正绑定到输入框；个别 ROM 的 dumpsys 格式不同，超时后交由上屏核对 + 重打兜底
    bind_deadline = time.time() + IME_BIND_TIMEOUT
    while time.time() < bind_deadline and not _ime_bound_to_field(driver):
        time.sleep(0.2)


def _restore_ime(driver: Any, previous: str) -> None:
    if previous and previous != UNICODE_IME_ID and "/" in previous:
        try:
            _shell(driver, ["ime", "set", previous])
        except Exception as e:  # 恢复失败不影响本次输入结果，但需留痕
            logger.warning(f"恢复原输入法 [{previous}] 失败: {e}")


def read_focused_input_text(driver: Any) -> Optional[str]:
    """从控件树读取当前聚焦输入框文本；无法判定时返回 None（不阻断流程）"""
    try:
        root = ET.fromstring(driver.page_source.encode("utf-8"))
    except Exception:
        return None
    edits = [n for n in root.iter() if "EditText" in n.attrib.get("class", "")]
    focused = [n for n in edits if n.attrib.get("focused") == "true"]
    target = (focused or edits[:1])
    return target[0].attrib.get("text", "") if target else None


def type_chinese_text(driver: Any, text: str) -> None:
    """切换 UnicodeIME 输入中文并恢复原输入法；输入后核对，不一致抛 InputMismatch"""
    ensure_unicode_ime_installed(driver)
    previous = _current_ime(driver)
    encoded = encode_imap_utf7(text)
    try:
        _activate_unicode_ime(driver)
        actual = _send_encoded(driver, text, encoded)
        # 输入法尚未接管输入框时，编码原文会被当作普通字符打出：清空后重打
        for _ in range(RAW_RETYPE_ATTEMPTS):
            if actual is None or encoded not in actual:
                break
            logger.warning(f"输入法未及时接管输入框，打出了编码原文 '{actual}'，清空后重新上屏")
            _shell(driver, ["input", "keyevent"] + ["67"] * (len(actual) + 2))  # KEYCODE_DEL
            time.sleep(0.5)
            actual = _send_encoded(driver, text, encoded)
    finally:
        _restore_ime(driver, previous)

    if actual is not None and text not in actual:
        raise InputMismatch(f"输入框实际内容为 '{actual}'，与期望输入 '{text}' 不一致")


def _send_encoded(driver: Any, text: str, encoded: str) -> Optional[str]:
    logger.info(f"原生 ADB UnicodeIME 中文上屏: '{text}' (UTF-7: {encoded})")
    # 单引号包裹，防止 /system/bin/sh 将 & 解释为后台任务
    _shell(driver, ["input", "text", f"'{encoded}'"])
    time.sleep(0.3)
    return read_focused_input_text(driver)
