import base64
import re
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Tuple, Optional
from appium import webdriver

class PerceptionMode:
    """
    分层感知三级火箭架构模式
    - HIERARCHY_TEXT (Level 1): 原生 UI 树丰富，毫秒级纯文本短路 (跳过图片上传与端侧 OCR)
    - OCR_TEXT (Level 2): 原生稀疏，但端侧本地 OCR 补齐丰富，采用轻量纯文本决策
    - FULL_VISION (Level 3): 纯图标、自绘图形、验证码滑块、或遇阻断升格，启用多模态全量视觉
    """
    HIERARCHY_TEXT = "HIERARCHY_TEXT"
    OCR_TEXT = "OCR_TEXT"
    FULL_VISION = "FULL_VISION"


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
    def wait_for_visual_settling(driver: webdriver.Remote, max_wait: float = 2.5, interval: float = 0.15) -> Tuple[str, bytes]:
        """
        自适应视觉静默检测门禁 (Visual Settling Guard)
        在动作派发后，智能探测屏幕帧指纹变动率；
        一旦画面连续两次变动率低于 2.5%（转场或数据已渲染稳定），提前极速放行（通常仅需 200~400ms）；
        若页面存在持续动画或慢请求，最多等待 max_wait 秒，彻底消灭白屏/半加载导致的假阴性决策。
        """
        import time
        from PIL import Image
        import io

        last_sample = None
        start_time = time.time()
        last_b64, last_bytes = None, None

        while True:
            b64_img, raw_bytes = ScreenParser.capture_screen(driver)
            last_b64, last_bytes = b64_img, raw_bytes

            # 极速生成 32x32 灰度指纹
            try:
                img = Image.open(io.BytesIO(raw_bytes)).convert("L").resize((32, 32))
                current_sample = img.tobytes()
            except Exception:
                break

            if last_sample is not None:
                diff_count = sum(1 for a, b in zip(last_sample, current_sample) if abs(a - b) > 18)
                diff_ratio = diff_count / 1024.0
                if diff_ratio < 0.025:  # 画面变动率 < 2.5%，即刻静止放行
                    break

            last_sample = current_sample
            if time.time() - start_time >= max_wait:
                break
            time.sleep(interval)

        return last_b64, last_bytes

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
                    "is_input": is_input,
                    "center": (center_x, center_y) if center_x is not None else None,
                    "bounds": bounds
                })
                index += 1

        return elements

    @staticmethod
    def is_hierarchy_rich(elements: List[Dict[str, Any]], goal: Optional[str] = None) -> bool:
        """
        评估当前原生 UI 控件树是否信息充沛 (Level 1 门禁)：
        若包含丰富的文本、输入框、可交互组件且未检测到需视觉参与的图形滑块/拼图，
        即可直接通过结构化纯文本完成毫秒级决策，跳过端侧 OCR 与视觉大模型图片上传。
        """
        if not elements:
            return False

        # 检查是否包含需视觉攻坚的图形滑块/拼图行为验证
        captcha_keywords = [
            "按住滑块", "拖动滑块", "拖动下方滑块", "完成拼图", "拖到最右边",
            "点击倒立文字", "安全验证", "行为验证", "验证码拼图", "点触验证", "旋转图片"
        ]
        for el in elements:
            t = (el.get("text") or el.get("desc") or "").strip()
            if any(k in t for k in captcha_keywords):
                return False

        # 过滤系统状态栏杂质 (如 com.android.systemui)，统计应用有效文本元素与交互元素
        meaningful_elements = []
        for el in elements:
            res_id = el.get("resource_id", "")
            if "com.android.systemui" in res_id:
                continue
            t = (el.get("text") or el.get("desc") or "").strip()
            is_inp = el.get("is_input", False) or "EditText" in el.get("class", "")
            is_click = el.get("clickable", False)
            if (t and len(t) >= 1) or is_inp or (is_click and res_id):
                meaningful_elements.append(el)

        # 1. 目标命中快速短路：若 UI 树中已明确包含测试目标关键词 (双向匹配)
        if goal:
            goal_clean = goal.strip()
            hit_elements = []
            for el in meaningful_elements:
                t = (el.get("text") or el.get("desc") or "").strip()
                if len(t) >= 2 and (t in goal_clean or goal_clean in t):
                    hit_elements.append(el)
            if hit_elements and len(meaningful_elements) >= 3:
                return True

        # 2. 通用充沛度基准：>= 4 个有效控件，且至少 2 个包含非空文本
        text_count = sum(1 for el in meaningful_elements if (el.get("text") or el.get("desc")))
        interactive_count = sum(1 for el in meaningful_elements if el.get("clickable") or el.get("is_input"))

        return len(meaningful_elements) >= 4 and text_count >= 2 and interactive_count >= 1

    @staticmethod
    def evaluate_perception_mode(
        hierarchy_elements: List[Dict[str, Any]],
        ocr_elements: Optional[List[Dict[str, Any]]] = None,
        goal: Optional[str] = None,
        force_vision: bool = False
    ) -> Tuple[str, float, str]:
        """
        综合评估页面感知分层模式（Perception Rocket）：
        - HIERARCHY_TEXT (Level 1): 原生 UI 树丰富，毫秒级纯文本短路 (跳过图片上传与端侧 OCR)
        - OCR_TEXT (Level 2): 原生稀疏，但端侧本地 OCR 补齐丰富，采用轻量纯文本决策
        - FULL_VISION (Level 3): 纯图标、自绘图形、验证码滑块、或遇阻断升格，启用多模态全量视觉
        返回: (perception_mode, confidence, reason)
        """
        if force_vision:
            return (PerceptionMode.FULL_VISION, 1.0, "触发重试或阻断升格门禁，强制启用多模态视觉模型")

        all_elements = list(hierarchy_elements or []) + list(ocr_elements or [])
        combined_texts = " ".join((e.get("text") or e.get("desc") or "") for e in all_elements)

        # 检查是否包含需视觉攻坚的图形滑块/拼图行为验证
        captcha_keywords = [
            "按住滑块", "拖动滑块", "拖动下方滑块", "完成拼图", "拖到最右边",
            "点击倒立文字", "安全验证", "行为验证", "验证码拼图", "点触验证", "旋转图片"
        ]
        if any(k in combined_texts for k in captcha_keywords):
            return (PerceptionMode.FULL_VISION, 0.95, "检测到图形滑块/拼图验证码，需要多模态视觉精确定位")

        # Level 1: 原生 UI 树信息充沛
        if ScreenParser.is_hierarchy_rich(hierarchy_elements, goal=goal):
            m_count = sum(1 for e in hierarchy_elements if (e.get("text") or e.get("desc") or e.get("is_input")))
            return (PerceptionMode.HIERARCHY_TEXT, 0.95, f"原生 UI 树信息充沛（{m_count} 个有效控件），跳过视觉图片上传采用纯文本极速决策")

        # Level 2: 端侧本地 OCR 补齐后具备足够文字或命中目标
        if ocr_elements:
            valid_ocr = [e for e in ocr_elements if e.get("text") and len(e.get("text", "").strip()) >= 2]
            if len(valid_ocr) >= 3 or (goal and any((e.get("text", "") in goal or goal in e.get("text", "")) for e in valid_ocr if len(e.get("text", "")) >= 2)):
                return (PerceptionMode.OCR_TEXT, 0.85, f"原生 UI 树稀疏，端侧本地 OCR 成功补齐文字（{len(valid_ocr)} 个视觉文字），采用轻量纯文本决策")

        # Level 3: 兜底全量视觉攻坚
        return (PerceptionMode.FULL_VISION, 0.90, "界面元素稀疏或纯图标图元，启用视觉大模型攻坚")

    @staticmethod
    def get_screen_summary(
        driver: webdriver.Remote, 
        wait_settling: bool = False,
        skip_ocr_if_rich: bool = True,
        goal: Optional[str] = None,
        force_vision: bool = False
    ) -> Dict[str, Any]:
        """组合截图、原生控件树与分层感知三级火箭架构，生成供 AI 极速决策的页面概览"""
        elements = ScreenParser.parse_elements(driver)

        # Level 1: 评估原生 UI 树是否足够充沛
        is_rich = ScreenParser.is_hierarchy_rich(elements, goal=goal)
        ocr_elements = []
        ocr_cached = False

        if skip_ocr_if_rich and is_rich and not force_vision:
            # 原生 UI 树丰富，直接短路跳过端侧 OCR 与多帧视觉防抖，执行单次极速截屏保持现场
            b64_img, raw_bytes = ScreenParser.capture_screen(driver)
            mode, confidence, reason = ScreenParser.evaluate_perception_mode(
                hierarchy_elements=elements,
                ocr_elements=[],
                goal=goal,
                force_vision=False
            )
        else:
            # Level 2 / Level 3: 原生稀疏或强制视觉，执行端侧本地 OCR 补齐与多帧防抖
            if wait_settling:
                b64_img, raw_bytes = ScreenParser.wait_for_visual_settling(driver)
            else:
                b64_img, raw_bytes = ScreenParser.capture_screen(driver)

            try:
                from core.vision_ocr import VisionOCR
                ocr_elements, ocr_cached = VisionOCR.recognize_elements(raw_bytes)
            except Exception:
                ocr_elements, ocr_cached = [], False

            mode, confidence, reason = ScreenParser.evaluate_perception_mode(
                hierarchy_elements=elements,
                ocr_elements=ocr_elements,
                goal=goal,
                force_vision=force_vision
            )

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
            "ocr_cached": ocr_cached,
            "perception_mode": mode,
            "perception_confidence": confidence,
            "perception_reason": reason,
            "hierarchy_rich": is_rich
        }
