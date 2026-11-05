# -*- coding: utf-8 -*-
"""真机中文输入：不得截断/拼音降级；缺组件自动安装；输入后恢复原输入法；回读核对"""
from types import SimpleNamespace

import pytest

import ai_engine.chinese_input as ci

GBOARD = "com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME"


class FakePhone:
    def __init__(self, installed=True, ime_switch_works=True, field_text_after=None, install_ok=True):
        self.installed = installed
        self.ime_switch_works = ime_switch_works
        self.install_ok = install_ok
        self.current_ime = GBOARD
        self.typed = []
        self.calls = []
        self.field_text_after = field_text_after
        self.raw_first_n = 0
        self.field = None

    def execute_adb(self, args, timeout=15):
        self.calls.append(args)
        out = ""
        if args[0] == "install":
            self.installed = self.install_ok
            out = "Success" if self.install_ok else "Failure [INSTALL_FAILED]"
        elif args[:3] == ["shell", "pm", "list"]:
            out = f"package:{ci.UNICODE_IME_PACKAGE}\n" if self.installed else ""
        elif args[:4] == ["shell", "settings", "get", "secure"]:
            out = self.current_ime
        elif args[:3] == ["shell", "ime", "set"]:
            if args[3] != ci.UNICODE_IME_ID or (self.installed and self.ime_switch_works):
                self.current_ime = args[3]
        elif args[:3] == ["shell", "input", "text"]:
            self.typed.append(args[3])
            if self.raw_first_n > 0:  # 模拟输入法尚未接管：编码原文被当作普通字符打出
                self.raw_first_n -= 1
                self.field = args[3].strip("'")
            else:
                self.field = None
        elif args[:3] == ["shell", "dumpsys", "input_method"]:
            out = f"  mCurId={self.current_ime} mHaveConnection=true mBoundToMethod=true"
        return SimpleNamespace(stdout=out, stderr="", returncode=0)

    @property
    def page_source(self):
        text = self.field if self.field is not None else (
            self.field_text_after if self.field_text_after is not None else "精装两居")
        from xml.sax.saxutils import quoteattr  # 与 uiautomator dump 一致：属性值做 XML 转义
        return f'<hierarchy><node class="android.widget.EditText" focused="true" text={quoteattr(text)}/></hierarchy>'


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(ci, "IME_SWITCH_TIMEOUT", 0.3)
    monkeypatch.setattr(ci.time, "sleep", lambda *_: None)


def _decode_imap_utf7(s: str) -> str:
    import base64, re
    def repl(m):
        body = m.group(1)
        if body == "":
            return "&"
        b64 = body.replace(",", "/")
        return base64.b64decode(b64 + "=" * (-len(b64) % 4)).decode("utf-16be")
    return re.sub(r"&([^-]*)-", repl, s)


@pytest.mark.parametrize("text", ["精装两居", "A&B 两居", "三室 2 厅", "精装两居&近地铁"])
def test_utf7_encoding_roundtrips_full_text(text):
    assert _decode_imap_utf7(ci.encode_imap_utf7(text)) == text


def test_types_full_text_and_restores_original_ime():
    phone = FakePhone()
    ci.type_chinese_text(phone, "精装两居")
    assert phone.typed == [f"'{ci.encode_imap_utf7('精装两居')}'"]
    assert _decode_imap_utf7(phone.typed[0].strip("'")) == "精装两居"
    assert phone.current_ime == GBOARD  # 输入后恢复用户原输入法


def test_auto_installs_unicode_ime_when_missing(monkeypatch, tmp_path):
    apk = tmp_path / "settings_apk-debug.apk"
    apk.write_bytes(b"apk")
    monkeypatch.setattr(ci, "APK_CANDIDATES", [apk])
    phone = FakePhone(installed=False)
    ci.type_chinese_text(phone, "精装两居")
    assert ["install", "-r", "-g", str(apk)] in phone.calls
    assert phone.typed


def test_missing_component_without_apk_fails_loudly_never_pinyin(monkeypatch, tmp_path):
    monkeypatch.setattr(ci, "APK_CANDIDATES", [tmp_path / "nope.apk"])
    phone = FakePhone(installed=False)
    with pytest.raises(ci.ChineseInputUnavailable, match="appium driver install"):
        ci.type_chinese_text(phone, "精装两居")
    assert phone.typed == []  # 绝不输入截断的拼音


def test_ime_switch_timeout_restores_and_raises():
    phone = FakePhone(ime_switch_works=False)
    with pytest.raises(ci.ChineseInputUnavailable):
        ci.type_chinese_text(phone, "精装两居")
    assert phone.typed == [] and phone.current_ime == GBOARD


def test_mismatch_after_typing_is_reported():
    phone = FakePhone(field_text_after="精装")
    with pytest.raises(ci.InputMismatch, match="精装两居"):
        ci.type_chinese_text(phone, "精装两居")


def test_executor_no_longer_truncates_to_pinyin():
    from pathlib import Path
    src = Path(ci.__file__).resolve().parent.joinpath("action_executor.py").read_text(encoding="utf-8")
    assert "lazy_pinyin" not in src and "type_chinese_text(self.driver, text)" in src


def test_raw_encoded_text_is_cleared_and_retyped():
    """真机实测：刚装好/刚切换的输入法未接管输入框时会打出 '&fL6IxU4kXEU-'，应清空后自动重打"""
    phone = FakePhone()
    phone.raw_first_n = 1
    ci.type_chinese_text(phone, "精装两居")
    assert len(phone.typed) == 2
    assert any(c[:3] == ["shell", "input", "keyevent"] and "67" in c for c in phone.calls)
    assert phone.current_ime == GBOARD


def test_waits_for_ime_binding_before_typing():
    phone = FakePhone()
    ci.type_chinese_text(phone, "精装两居")
    dumps = [i for i, c in enumerate(phone.calls) if c[:3] == ["shell", "dumpsys", "input_method"]]
    first_type = next(i for i, c in enumerate(phone.calls) if c[:3] == ["shell", "input", "text"])
    assert dumps and dumps[0] < first_type
