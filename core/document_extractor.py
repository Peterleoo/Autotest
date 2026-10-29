# -*- coding: utf-8 -*-
import os
import re
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional

class DocumentExtractor:
    """
    轻量高鲁棒性多模态文档与图像解析引擎 (Document & Vision Extractor)
    严格遵循 KISS 原则，内置原生 DOCX/PDF/TXT/MD 解析能力，零脆弱外部网络依赖。
    """

    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """从给定文件中提取可供 AI 决策模型消费的结构化纯文本需求"""
        p = Path(file_path)
        if not p.exists():
            return ""

        suffix = p.suffix.lower()

        # 1. 文本类格式 (.txt, .md, .json, .csv, .log)
        if suffix in [".txt", ".md", ".markdown", ".json", ".csv", ".log"]:
            return cls._extract_plain_text(p)

        # 2. Word 文档 (.docx) - 基于原生 Zip & XML 解析，极速且零依赖
        if suffix == ".docx":
            return cls._extract_docx_native(p)

        # 3. PDF 文档 (.pdf)
        if suffix == ".pdf":
            return cls._extract_pdf(p)

        return ""

    @classmethod
    def _extract_plain_text(cls, path: Path) -> str:
        encodings = ["utf-8", "gbk", "gb2312", "latin-1"]
        for enc in encodings:
            try:
                return path.read_text(encoding=enc).strip()
            except (UnicodeDecodeError, Exception):
                continue
        return ""

    @classmethod
    def _extract_docx_native(cls, path: Path) -> str:
        """基于 Python 标准库 zipfile + xml 原生提取 docx 段落与表格文本"""
        try:
            with zipfile.ZipFile(path) as docx_zip:
                xml_content = docx_zip.read("word/document.xml")
                tree = ET.fromstring(xml_content)
                # WordprocessingML 命名空间
                namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                
                paragraphs = []
                # 遍历所有段落
                for p_elem in tree.findall(".//w:p", namespaces):
                    text_pieces = [t.text for t in p_elem.findall(".//w:t", namespaces) if t.text]
                    if text_pieces:
                        paragraphs.append("".join(text_pieces))
                
                # 遍历所有表格
                for table in tree.findall(".//w:tbl", namespaces):
                    for row in table.findall(".//w:tr", namespaces):
                        cells = []
                        for cell in row.findall(".//w:tc", namespaces):
                            cell_texts = [t.text for t in cell.findall(".//w:t", namespaces) if t.text]
                            cells.append(" ".join(cell_texts) if cell_texts else "")
                        if any(cells):
                            paragraphs.append(" | ".join(cells))
                
                return "\n".join(paragraphs).strip()
        except Exception as e:
            return f"[DOCX 解析提示: {str(e)}]"

    @classmethod
    def _extract_pdf(cls, path: Path) -> str:
        """提取 PDF 文本，优先使用 pypdf，次选纯流提取"""
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            pages_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages_text.append(f"--- Page {i+1} ---\n{text}")
            return "\n\n".join(pages_text).strip()
        except Exception:
            # 基础文本流容错匹配
            try:
                content = path.read_bytes()
                # 提取 PDF 中的 BT...ET 文本流段落
                matches = re.findall(rb"\((.*?)\)\s*Tj", content)
                if matches:
                    extracted = [m.decode("utf-8", errors="ignore") for m in matches if len(m) > 1]
                    return "\n".join(extracted[:200]).strip()
            except Exception:
                pass
            return "[PDF 需求文档已挂载]"

    @classmethod
    def get_file_metadata(cls, file_path: str, original_filename: str = "") -> Dict[str, Any]:
        """获取附件的统一元数据描述字典"""
        p = Path(file_path)
        if not p.exists():
            return {}

        suffix = p.suffix.lower()
        size_bytes = p.stat().st_size
        
        # 格式化文件大小
        if size_bytes < 1024:
            size_str = f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f}KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.1f}MB"

        is_image = suffix in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]
        is_doc = suffix in [".docx", ".doc", ".pdf", ".md", ".txt", ".json", ".csv"]

        meta: Dict[str, Any] = {
            "filename": original_filename or p.name,
            "saved_name": p.name,
            "path": str(p),
            "size": size_str,
            "size_bytes": size_bytes,
            "suffix": suffix,
            "is_image": is_image,
            "is_doc": is_doc,
            "url": f"/api/uploads/{p.name}"
        }

        if is_image:
            try:
                from PIL import Image
                with Image.open(p) as img:
                    meta["width"] = img.width
                    meta["height"] = img.height
            except Exception:
                pass

        if is_doc:
            full_text = cls.extract_text(str(p))
            meta["extracted_text"] = full_text
            meta["char_count"] = len(full_text)
            # 截取前 300 字符作为预览摘要
            meta["preview_text"] = (full_text[:280] + "...") if len(full_text) > 300 else full_text

        return meta
