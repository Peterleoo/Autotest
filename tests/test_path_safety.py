# -*- coding: utf-8 -*-
"""P0-2 路径穿越防护：所有接收文件名的接口必须拒绝逃逸出基目录的路径"""
import asyncio
import inspect
import io

import pytest
from fastapi import HTTPException, UploadFile

import web.app as web_app
from config.settings import settings
from core.report_generator import ReportGenerator
from web.path_safety import safe_path

TRAVERSALS = ["../secret.py", "..\\secret.py", "sub/../../secret.py", "", "a\x00b.py"]


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    base = tmp_path / "base"
    for name in ("solidified", "apps", "uploads", "md"):
        (base / name).mkdir(parents=True)
    (base / "secret.py").write_text("SECRET = 1", encoding="utf-8")
    (base / "solidified" / "secret.py").write_text("x = 1", encoding="utf-8")
    monkeypatch.setattr(settings, "SOLIDIFIED_DIR", base / "solidified")
    monkeypatch.setattr(settings, "APPS_DIR", base / "apps")
    monkeypatch.setattr(web_app, "UPLOADS_DIR", base / "uploads")
    monkeypatch.setattr(web_app, "BASE_DIR", base / "solidified")
    monkeypatch.setattr(ReportGenerator, "MARKDOWN_DIR", base / "md")
    return base


def _status(fn, *args):
    with pytest.raises(HTTPException) as exc:
        result = fn(*args)
        if inspect.iscoroutine(result):
            asyncio.run(result)
    return exc.value.status_code


@pytest.mark.parametrize("name", TRAVERSALS + ["/etc/passwd", "C:\\Windows\\win.ini"])
def test_safe_path_rejects_escape(tmp_path, name):
    with pytest.raises(HTTPException) as exc:
        safe_path(tmp_path, name)
    assert exc.value.status_code == 400


def test_safe_path_allows_nested_file(tmp_path):
    assert safe_path(tmp_path, "app_x/test_a.py") == (tmp_path / "app_x" / "test_a.py").resolve()


@pytest.mark.parametrize("name", TRAVERSALS)
def test_file_endpoints_reject_traversal(dirs, name):
    assert _status(web_app.get_solidified_case_content, name) == 400
    assert _status(web_app.run_pytest, name) == 400
    assert _status(web_app.delete_solidified_case, name) == 400
    assert _status(web_app.delete_app_package, name) == 400
    assert _status(web_app.install_app_to_device, None, name) == 400
    assert _status(web_app.get_uploaded_attachment, name) == 400
    if name:
        assert _status(web_app.replay_deliverable, {"safeRef": name}) == 400
    assert (dirs / "secret.py").exists()


def test_report_markdown_rejects_traversal(dirs):
    assert _status(web_app.get_report_markdown, "..\\..\\..\\secret") == 400


def test_upload_app_rejects_traversal_filename(dirs):
    upload = UploadFile(file=io.BytesIO(b"x"), filename="../evil.apk")
    assert _status(web_app.upload_app_package, upload) == 400
    assert not (dirs / "evil.apk").exists()


def test_content_reads_file_inside_base(dirs):
    data = asyncio.run(web_app.get_solidified_case_content("secret.py"))
    assert data["content"] == "x = 1"
