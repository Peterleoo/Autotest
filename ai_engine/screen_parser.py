import base64
import re
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Tuple
from appium import webdriver

class ScreenParser:
    """
    负责提取屏幕截图与界面树结构，生成供 AI 决策的精简视图
    """
    @staticmethod
    def capture_screen(driver: webdriver.Remote) -> Tuple[str, bytes]:
        """截取当前屏幕，返回供模型理解的轻量 base64 字符串与供高精度 OCR 的原始 bytes"""
        b64_str = driver.get_screenshot_as_base64()
        raw_bytes = base64.b64decode(b64_str)
        # 为大模型生成轻量 JPEG 缩略图（40KB），原图（1.5MB）留给 OCR 保持高精度坐标
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(raw_bytes))
            img.thumbnail((540, 1170))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=75)
            model_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception:
            model_b64 = b64_str
        return model_b64, raw_bytes

    @staticmethod
    def parse_elements(driver: webdriver.Remote) -> List[Dict[str, Any]]:
        """
        从 Page Source XML 中提取所有可交互或关键文本元素，并赋予编号
        """
        xml_source = driver.page_source
        elements = []

        try:
            root = ET.fromstring(xml_source.encode("utf-8"))
        except Exception:
            # 兼容某些 malformed XML
            return []

        index = 1
        for node in root.iter():
            # 过滤不可见或纯容器节点
            attrib = node.attrib
            text = attrib.get("text", "").strip()
            desc = attrib.get("content-desc", "").strip() or attrib.get("name", "").strip()
            res_id = attrib.get("resource-id", "").strip() or attrib.get("id", "").strip()
            cls_name = attrib.get("class", "").strip() or attrib.get("type", "").strip()
            bounds = attrib.get("bounds", "") # 例如 "[0,100][1080,300]"

            # 判断是否为关键/可交互元素
            is_clickable = attrib.get("clickable", "false").lower() == "true"
            is_input = "EditText" in cls_name or "TextField" in cls_name
            has_content = bool(text or desc)

            if is_clickable or is_input or has_content:
                # 解析 bounds
                center_x, center_y = None, None
                if bounds:
                    match = re.findall(r"\[(\d+),(\d+)\]", bounds)
                    if len(match) == 2:
                        x1, y1 = map(int, match[0])
                        x2, y2 = map(int, match[1])
                        center_x = (x1 + x2) // 2
                        center_y = (y1 + y2) // 2

                elements.append({
                    "index": index,
                    "text": text,
                    "desc": desc,
                    "resource_id": res_id,
                    "class": cls_name.split(".")[-1], # 简写类名
                    "clickable": is_clickable,
                    "center": (center_x, center_y) if center_x is not None else None,
                    "bounds": bounds
                })
                index += 1

        return elements

    @staticmethod
    def get_screen_summary(driver: webdriver.Remote) -> Dict[str, Any]:
        """组合截图、原生控件树与视觉 OCR 识别，生成具备高精度视觉透视能力的页面概览"""
        b64_img, raw_bytes = ScreenParser.capture_screen(driver)
        elements = ScreenParser.parse_elements(driver)

        # 引入视觉 OCR 图片识别（解决 Hybrid / 自绘应用原生控件树缺失、看不清界面的致命痛点）
        ocr_cached = False
        try:
            from core.vision_ocr import VisionOCR
            ocr_elements, ocr_cached = VisionOCR.recognize_elements(raw_bytes)
        except Exception:
            ocr_elements, ocr_cached = [], False

        # 智能融合：将 OCR 识别出的高精度视觉文字元素补齐入列表
        merged_elements = list(elements)
        existing_texts = {e["text"] for e in merged_elements if e.get("text")}

        for oe in ocr_elements:
            t = oe["text"]
            # 过滤顶部系统时间/信号等杂质
            if len(t) < 2 or any(k in t for k in ["紧急", "B/S", "蕊", "450"]):
                continue
            if t not in existing_texts and not any(t in ext for ext in existing_texts):
                merged_elements.append(oe)
                existing_texts.add(t)

        # 统一重新编号
        for idx, el in enumerate(merged_elements, start=1):
            el["index"] = idx

        # 形成结构化元素明细供 AI 决策
        element_lines = []
        for el in merged_elements:
            info = f"[{el['index']}] 类别:{el.get('class', 'Element')}"
            if el.get("text"):
                info += f" 文本:'{el['text']}'"
            if el.get("desc") and el.get("desc") != el.get("text"):
                info += f" 描述:'{el['desc']}'"
            if el.get("resource_id"):
                info += f" ID:'{el['resource_id']}'"
            if el.get("center"):
                info += f" 屏幕坐标:{el['center']}"
            if el.get("clickable"):
                info += " [可交互]"
            element_lines.append(info)

        return {
            "image_b64": b64_img,
            "raw_bytes": raw_bytes,
            "elements": merged_elements,
            "element_summary_text": "\n".join(element_lines),
            "ocr_cached": ocr_cached
        }
