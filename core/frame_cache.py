# -*- coding: utf-8 -*-
"""
感知缓存：减少真机端重复截屏与 uiautomator dump（两者都是高耗电操作）
- 稳定帧：视觉稳定检测截到的最后一帧，供紧随其后的感知直接使用（仅消费一次、短时有效）
- UI 树：严格屏幕指纹不变且期间未下发任何输入动作时复用上一次 dump 结果
任何输入类 ADB 指令（点击/滑动/输入/按键/启动应用）都会立即使缓存失效。
"""
import copy
import hashlib
import io
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

SETTLED_FRAME_MAX_AGE = 1.0   # 稳定帧仅在 1 秒内、且无新动作时可复用
UI_TREE_MAX_AGE = 30.0        # UI 树复用上限，防止长时间静止后系统弹窗等无视觉差异的变化被忽略
STATUS_BAR_RATIO = 0.05       # 计算严格指纹时裁掉顶部状态栏（时钟/电量变化不应使缓存失效）

_lock = threading.Lock()
_settled_frames: Dict[int, Tuple[float, str, bytes]] = {}
_ui_trees: Dict[int, Tuple[float, str, List[Dict[str, Any]]]] = {}

INPUT_COMMAND_MARKERS = ("input", "am start", "monkey", "keyevent")


def strict_fingerprint(image_bytes: bytes) -> Optional[str]:
    """严格屏幕指纹：裁掉状态栏后按 1/4 分辨率灰度精确哈希，任何文字/控件变化都会改变指纹"""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        w, h = img.size
        img = img.crop((0, int(h * STATUS_BAR_RATIO), w, h)).resize((max(1, w // 4), max(1, h // 4)))
        return hashlib.sha1(img.tobytes()).hexdigest()
    except Exception:
        return None


def remember_settled_frame(owner: Any, b64_img: str, raw_bytes: bytes) -> None:
    if raw_bytes:
        with _lock:
            _settled_frames[id(owner)] = (time.time(), b64_img, raw_bytes)


def consume_settled_frame(owner: Any) -> Optional[Tuple[str, bytes]]:
    with _lock:
        entry = _settled_frames.pop(id(owner), None)
    if entry and time.time() - entry[0] <= SETTLED_FRAME_MAX_AGE:
        return entry[1], entry[2]
    return None


def remember_ui_tree(owner: Any, fingerprint: Optional[str], elements: List[Dict[str, Any]]) -> None:
    if fingerprint:
        with _lock:
            _ui_trees[id(owner)] = (time.time(), fingerprint, copy.deepcopy(elements))


def lookup_ui_tree(owner: Any, fingerprint: Optional[str]) -> Optional[List[Dict[str, Any]]]:
    if not fingerprint:
        return None
    with _lock:
        entry = _ui_trees.get(id(owner))
    if entry and entry[1] == fingerprint and time.time() - entry[0] <= UI_TREE_MAX_AGE:
        return copy.deepcopy(entry[2])
    return None


def invalidate(owner: Any) -> None:
    with _lock:
        _settled_frames.pop(id(owner), None)
        _ui_trees.pop(id(owner), None)


def is_input_command(cmd_args: List[str]) -> bool:
    joined = " ".join(str(a) for a in cmd_args)
    return "shell" in cmd_args and any(m in joined for m in INPUT_COMMAND_MARKERS)
