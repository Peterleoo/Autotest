import os
import io
import json
import logging
import hashlib
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("VisionOCR")

BASE_DIR = Path(__file__).resolve().parent.parent
HELPER_PS1 = BASE_DIR / "core" / "win_ocr_helper.ps1"

# OCR 内存缓存池与上一帧指纹记录
_LAST_OCR_FINGERPRINT: Optional[str] = None
_LAST_OCR_RESULTS: List[Dict[str, Any]] = []

def compute_image_fingerprint(image_bytes: bytes) -> str:
    """计算图像感知差异哈希 (dHash)，对毫秒级状态栏变动或微小渲染噪点具备容错性"""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert('L').resize((17, 16), Image.Resampling.BILINEAR)
        diff = []
        for row in range(16):
            for col in range(16):
                pixel_left = img.getpixel((col, row))
                pixel_right = img.getpixel((col + 1, row))
                diff.append(pixel_left > pixel_right)
        decimal_val = 0
        for idx, bit in enumerate(diff):
            if bit:
                decimal_val |= 1 << idx
        return f"{decimal_val:016x}"
    except Exception:
        return hashlib.md5(image_bytes).hexdigest()

def hamming_distance(h1: str, h2: str) -> int:
    try:
        val1 = int(h1, 16)
        val2 = int(h2, 16)
        return bin(val1 ^ val2).count('1')
    except Exception:
        return 999 if h1 != h2 else 0

class VisionOCR:
    """
    Windows 原生视觉 OCR 识别器：
    利用 Windows 10/11 原生深度优化的 zh-Hans OCR 引擎，
    并内置屏幕感知指纹缓存：页面未实质变动时 0 Token、0 耗时复用上一次识别结果。
    """
    @staticmethod
    def recognize_elements(image_bytes: bytes, use_cache: bool = True) -> Tuple[List[Dict[str, Any]], bool]:
        global _LAST_OCR_FINGERPRINT, _LAST_OCR_RESULTS
        if not image_bytes:
            return [], False

        # 1. 计算当前截屏感知指纹
        current_fp = compute_image_fingerprint(image_bytes)

        # 2. 判断是否命中缓存（汉明距离 == 0，即屏幕完全无变动，避免轮播图相似帧误判）
        if use_cache and _LAST_OCR_FINGERPRINT is not None and _LAST_OCR_RESULTS:
            dist = hamming_distance(current_fp, _LAST_OCR_FINGERPRINT)
            if dist == 0:
                logger.info(f"⚡ [OCR缓存命中] 屏幕指纹完全一致，0 耗时复用上一次识别的 {len(_LAST_OCR_RESULTS)} 个元素！")
                # 返回深拷贝避免外界篡改缓存
                import copy
                cached_res = copy.deepcopy(_LAST_OCR_RESULTS)
                for item in cached_res:
                    item["cached"] = True
                return cached_res, True

        # 3. 屏幕实质改变，调用 OCR 引擎进行高精度提取
        # 写入临时图片文件
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        try:
            cmd = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", str(HELPER_PS1),
                "-ImagePath", tmp_path
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=20)
            stdout_bytes = res.stdout or b""
            if res.returncode == 0 and stdout_bytes.strip():
                # Windows PowerShell 5 默认输出 GBK，PowerShell 7 通常输出 UTF-8，双通道兼容
                try:
                    raw_json = stdout_bytes.decode("utf-8-sig")
                except UnicodeDecodeError:
                    raw_json = stdout_bytes.decode("gb18030", errors="replace")
                raw_json = raw_json.strip()
                data = None

                # PowerShell 的 ConvertTo-Json 在只有一条结果时会输出对象而不是数组，
                # 因此先整体解析，再兼容数组/带前后噪声的文本。
                try:
                    data = json.loads(raw_json)
                except Exception:
                    for left, right in [("[", "]"), ("{", "}")]:
                        start = raw_json.find(left)
                        end = raw_json.rfind(right) + 1
                        if start != -1 and end > start:
                            try:
                                data = json.loads(raw_json[start:end])
                                break
                            except Exception:
                                data = None

                if isinstance(data, dict):
                    data = [data]
                if not isinstance(data, list):
                    logger.warning(f"OCR 输出无法解析为元素数组: {raw_json[:200]}")
                    data = []

                elements = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    text = str(item.get("text", "")).strip()
                    # 清洗连带的空格（例如 "用 密 码 登 录" -> "用密码登录"）
                    clean_text = "".join(text.split())
                    center = item.get("center") or [540, 960]
                    if not isinstance(center, (list, tuple)) or len(center) < 2:
                        center = [540, 960]
                    bounds = item.get("bounds", "")

                    elements.append({
                        "index": item.get("index"),
                        "text": clean_text,
                        "raw_text": text,
                        "desc": clean_text,
                        "resource_id": "",
                        "class": "VisionTextElement",
                        "clickable": True,
                        "center": (int(center[0]), int(center[1])),
                        "bounds": bounds,
                        "source": "vision_ocr"
                    })
                logger.info(f"视觉 OCR 成功提取屏幕文字元素: {len(elements)} 个")
                _LAST_OCR_FINGERPRINT = current_fp
                _LAST_OCR_RESULTS = elements
                return elements, False
            else:
                err_text = (res.stderr or b"").decode("utf-8", errors="replace")
                logger.warning(f"OCR 识别执行异常: {err_text}")
        except Exception as e:
            logger.warning(f"视觉 OCR 识别失败: {e}")
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        return [], False
