# -*- coding: utf-8 -*-
"""测试报告与需求附件接口"""
from fastapi import APIRouter
import re
import glob
from datetime import datetime
from pathlib import Path
from typing import List
from fastapi import UploadFile, File, Form
import uuid
from fastapi.responses import JSONResponse, Response, FileResponse
from web.path_safety import safe_path
from core.report_generator import ReportGenerator
from core.document_extractor import DocumentExtractor

from web.shared import (
    UPLOADS_DIR,
    logger,
)

router = APIRouter()


@router.post("/api/upload")
async def upload_requirement_attachment(files: List[UploadFile] = File(...)):
    """
    多模态测试需求资产上传中心 (Antigravity 范式)
    支持文档 (.docx, .pdf, .md, .txt, .json) 与视觉参考图 (.png, .jpg, .jpeg, .webp)
    内置轻量零依赖文本提取与元数据构建
    """
    try:
        uploaded_results = []
        for f in files:
            if not f.filename:
                continue
            orig_name = f.filename
            safe_stem = re.sub(r"[^\w\.-]", "_", Path(orig_name).stem)[:40]
            ext = Path(orig_name).suffix.lower()
            unique_name = f"up_{datetime.now().strftime('%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}_{safe_stem}{ext}"
            dest_file = UPLOADS_DIR / unique_name
            content = await f.read()
            dest_file.write_bytes(content)
            
            meta = DocumentExtractor.get_file_metadata(str(dest_file), original_filename=orig_name)
            uploaded_results.append(meta)
        return {"success": True, "files": uploaded_results}
    except Exception as e:
        logger.error(f"上传多模态需求资产失败: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "message": f"上传失败: {str(e)}"})


@router.get("/api/uploads/{filename}")
async def get_uploaded_attachment(filename: str):
    """安全获取已上传的多模态需求文档或测试截图"""
    file_path = safe_path(UPLOADS_DIR, filename)
    if not file_path.is_file():
        return JSONResponse(status_code=404, content={"error": "附件未找到"})
    
    suffix = file_path.suffix.lower()
    media_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".pdf": "application/pdf",
        ".txt": "text/plain; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".json": "application/json"
    }
    media_type = media_map.get(suffix, "application/octet-stream")
    return FileResponse(file_path, media_type=media_type)


@router.get("/api/reports")
async def get_reports():
    """获取所有交付物 Markdown 测试报告"""
    return {"reports": ReportGenerator.get_all_reports()}


@router.get("/api/reports/{session_id}/markdown")
async def get_report_markdown(session_id: str, download: bool = False):
    """获取或下载指定会话的 6 大维度全景 Markdown 测试报告"""
    target = safe_path(ReportGenerator.MARKDOWN_DIR, f"test_report_{session_id}.md")
    if target.parent != ReportGenerator.MARKDOWN_DIR.resolve():
        return Response(status_code=400, content=b"Invalid session id", media_type="text/plain")
    if not target.exists():
        candidates = list(ReportGenerator.MARKDOWN_DIR.glob(f"*{glob.escape(session_id)}*.md"))
        if candidates:
            target = candidates[0]
        else:
            return Response(status_code=404, content=b"Markdown test report not found", media_type="text/plain")

    content = target.read_text(encoding="utf-8")
    if download:
        return Response(
            content=content.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{target.name}"'}
        )
    return {"session_id": session_id, "filename": target.name, "content": content}


@router.post("/api/reports/delete")
async def delete_report(report_id: str = Form(...)):
    """删除指定的 Markdown 交付物测试报告"""
    safe_name = Path(report_id).stem
    md_file = safe_path(ReportGenerator.MARKDOWN_DIR, f"{safe_name}.md")
    if not md_file.exists():
        md_file = safe_path(ReportGenerator.MARKDOWN_DIR, f"test_report_{safe_name}.md")
    deleted = False
    try:
        if md_file.exists():
            md_file.unlink()
            deleted = True
        if deleted:
            return {"success": True, "message": f"Markdown 测试报告 [{safe_name}] 已成功删除"}
        return {"success": False, "message": "未找到对应的测试报告文件"}
    except Exception as e:
        return {"success": False, "message": f"删除报告失败: {e}"}
