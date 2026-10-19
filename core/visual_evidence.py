import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
SCREENSHOTS_DIR = REPORTS_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

class VisualEvidence:
    """
    负责生成和标注自动化测试的视觉证据截图（真机截图标记 / 本地推演高保真界面生成）
    """
    @staticmethod
    def annotate_real_screenshot(raw_bytes: bytes, step_idx: int, action: str, tap_pos: Optional[Tuple[int, int]] = None) -> str:
        """为真机实际截屏添加手势点击标记与步骤水印"""
        timestamp = int(time.time() * 1000)
        filename = f"step_{step_idx}_{action}_{timestamp}.png"
        filepath = SCREENSHOTS_DIR / filename

        import io
        img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        draw = ImageDraw.Draw(img)

        # 标记点击坐标（红圈水波纹效果）
        if tap_pos:
            x, y = tap_pos
            r = 30
            draw.ellipse((x - r, y - r, x + r, y + r), outline="#ef4444", width=5)
            draw.ellipse((x - r*2, y - r*2, x + r*2, y + r*2), outline="#f87171", width=2)
            draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill="#ef4444")

        # 底部添加测试水印
        w, h = img.size
        draw.rectangle((0, h - 60, w, h), fill="#0b0f19")
        # 简单字样
        text = f"STEP {step_idx}: [{action.upper()}] - {time.strftime('%H:%M:%S')}"
        draw.text((20, h - 45), text, fill="#38bdf8")

        img.save(filepath, "PNG")
        return f"/reports/screenshots/{filename}"
