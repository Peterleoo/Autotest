# -*- coding: utf-8 -*-
"""FastAPI 应用入口：创建应用、挂载中间件与静态目录、注册各业务路由"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from web.csrf import CSRFOriginMiddleware, allowed_origins_from_env
from core.report_generator import REPORTS_DIR
from web.shared import (
    BASE_DIR,
)

app = FastAPI(title="Autotest Web Console", description="移动端 AI 自动化测试操作平台")
app.add_middleware(CSRFOriginMiddleware, extra_allowed_origins=allowed_origins_from_env())
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")
STATIC_DIR = BASE_DIR / "web" / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

from web.routers import apps, cases, devices, reports, sessions, system  # noqa: E402

for _router_module in (devices, apps, sessions, cases, reports, system):
    app.include_router(_router_module.router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    response = templates.TemplateResponse("index.html", {"request": request})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# 向后兼容：保留 `from web.app import xxx` / `web.app.xxx` 的旧访问路径
from web.shared import (  # noqa: E402,F401
    ALL_SUGGESTED_CASES,
    BASE_DIR,
    KNOWN_APP_META,
    METADATA_FILE,
    UPLOADS_DIR,
    app_mgr,
    logger,
    resolve_target_device_id,
    task_mgr,
)
from web.routers.devices import (  # noqa: E402,F401
    DEVICE_LIST_TIMEOUT,
    _DEVICE_CACHE,
    _DEVICE_DIMENSIONS_CACHE,
    _build_ios_node,
    _device_list_fallback,
    _get_device_screen_dimensions,
    get_device_foreground_app,
    get_device_installed_apps,
    get_device_screenshot,
    get_devices,
    save_device_app_label,
    send_device_key,
    stream_device_screen,
    swipe_device,
    tap_device,
)
from web.routers.apps import (  # noqa: E402,F401
    check_app_installed,
    delete_app_package,
    download_from_qr,
    get_app_projects,
    get_apps,
    install_app_to_device,
    save_app_credentials,
    upload_app_package,
)
from web.routers.sessions import (  # noqa: E402,F401
    accept_session,
    append_session_message,
    approve_task_session,
    clarify_task_session,
    compact_session,
    create_task_session,
    delete_task_session,
    force_run_doc_suite,
    get_session_compatibility_matrix,
    get_session_deliverables,
    get_session_detail,
    get_session_raw_logs_endpoint,
    get_session_token_pressure,
    get_sessions_list,
    pause_task_session,
    rename_session,
    resolve_session_decision,
    resume_task_session,
    rework_session,
    stop_task_session,
)
from web.routers.cases import (  # noqa: E402,F401
    DEFAULT_PRESET_METADATA,
    auto_categorize_case,
    batch_run_solidified_cases,
    delete_solidified_case,
    get_deliverables_list,
    get_solidified_case_content,
    get_solidified_cases,
    list_test_suites_endpoint,
    load_cases_metadata,
    parse_case_timestamp,
    replay_deliverable,
    resolve_session_app_id,
    run_pytest,
    run_systemic_test_suite,
    save_cases_metadata,
    save_session_to_local_case,
    save_solidified_case,
    save_test_suite_endpoint,
    suggest_cases,
    synthesize_test_suite,
    webhook_trigger_regression,
)
from web.routers.reports import (  # noqa: E402,F401
    delete_report,
    get_report_markdown,
    get_reports,
    get_uploaded_attachment,
    upload_requirement_attachment,
)
from web.routers.system import (  # noqa: E402,F401
    auth_mgr,
    fetch_remote_models,
    get_antigravity_status,
    get_auth_status,
    get_config,
    get_env_status,
    start_antigravity_login,
    switch_antigravity_model,
    system_preflight,
    update_config,
    verify_invite,
)
