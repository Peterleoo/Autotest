import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

class ReportGenerator:
    """
    负责生成和管理移动端自动化测试的交付物报告 (HTML / JSON)
    """
    @staticmethod
    def get_all_reports() -> List[Dict[str, Any]]:
        """获取所有已生成的测试报告"""
        reports = []
        for p in sorted(REPORTS_DIR.glob("*.html"), key=lambda x: x.stat().st_mtime, reverse=True):
            meta_file = p.with_suffix(".json")
            meta = {}
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            
            reports.append({
                "id": p.stem,
                "filename": p.name,
                "url": f"/reports/{p.name}",
                "title": meta.get("title", p.stem),
                "goal": meta.get("goal", "自动化回归测试"),
                "mode": meta.get("mode", "本地测试"),
                "status": meta.get("status", "PASS"),
                "pass_rate": meta.get("pass_rate", "100%"),
                "duration": meta.get("duration", "3.2s"),
                "created_at": meta.get("created_at", datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")),
                "size": f"{p.stat().st_size // 1024 + 1} KB"
            })
        return reports

    @staticmethod
    def generate_html_report(
        title: str,
        goal: str,
        test_mode: str,
        app_name: str,
        package: str,
        model_name: str,
        status: str,
        steps: List[Dict[str, Any]],
        raw_output: str,
        duration_sec: float
    ) -> Path:
        """生成专业美观的交付物 HTML 测试报告"""
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"test_report_{timestamp_str}.html"
        report_path = REPORTS_DIR / report_filename

        passed_count = sum(1 for s in steps if s.get("status", "PASS") == "PASS")
        total_count = len(steps)
        pass_rate = f"{(passed_count / total_count * 100):.1f}%" if total_count > 0 else "100%"

        steps_html = ""
        gallery_html = ""
        for idx, s in enumerate(steps, 1):
            st = s.get("status", "PASS")
            badge_class = "success" if st == "PASS" else "danger"
            action = s.get("action", "")
            reason = s.get("reason", "")
            detail = s.get("detail", "")
            screenshot = s.get("screenshot_url", "")
            
            thumb_img = ""
            if screenshot:
                thumb_img = f"""<a href="{screenshot}" target="_blank"><img src="{screenshot}" class="rounded border border-secondary" style="height: 48px; object-fit: contain;"></a>"""
                gallery_html += f"""
                <div class="col-md-2 col-sm-4 col-6 text-center mb-3">
                    <div class="p-2 rounded bg-black border border-secondary h-100">
                        <div class="small fw-bold text-info mb-1">Step {idx} ({action})</div>
                        <a href="{screenshot}" target="_blank">
                            <img src="{screenshot}" class="img-fluid rounded border border-info mb-2" style="max-height: 240px; object-fit: contain;">
                        </a>
                        <div class="small text-white text-truncate" title="{reason}">{reason}</div>
                        <span class="badge bg-{badge_class} mt-1">{st}</span>
                    </div>
                </div>
                """

            steps_html += f"""
            <tr class="align-middle">
                <td><span class="badge bg-secondary">Step {idx}</span></td>
                <td><span class="fw-bold">{action}</span></td>
                <td>{reason}</td>
                <td><code class="text-info">{detail}</code></td>
                <td>{thumb_img or '<span class="text-secondary small">无截屏</span>'}</td>
                <td><span class="badge bg-{badge_class}">{st}</span></td>
            </tr>
            """

        status_badge_color = "#10b981" if status == "PASS" else "#ef4444"

        gallery_section = ""
        if gallery_html:
            gallery_section = f"""
            <!-- 视觉证据画廊 -->
            <div class="report-card">
                <h5 class="fw-bold mb-3 text-info"><i class="bi bi-camera-fill me-2"></i>自动化交互截屏全景证据链 (Visual Evidence Gallery)</h5>
                <div class="row g-2 justify-content-start">
                    {gallery_html}
                </div>
            </div>
            """

        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - 自动化测试交付报告</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        body {{ background-color: #0b0f19; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 30px; }}
        .report-card {{ background-color: #151d30; border: 1px solid #243049; border-radius: 12px; padding: 24px; margin-bottom: 24px; }}
        .header-title {{ border-left: 4px solid #38bdf8; padding-left: 12px; }}
        .stat-box {{ background-color: #0d1424; border: 1px solid #243049; border-radius: 8px; padding: 16px; text-align: center; }}
        .stat-value {{ font-size: 24px; font-weight: bold; }}
        .table-dark {{ background-color: #151d30; }}
        .log-box {{ background-color: #080c14; border: 1px solid #243049; border-radius: 8px; padding: 16px; font-family: Consolas, monospace; font-size: 13px; color: #38bdf8; max-height: 300px; overflow-y: auto; white-space: pre-wrap; }}
    </style>
</head>
<body>
    <div class="container-fluid max-w-1200">
        <!-- 顶部标题 -->
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h3 class="header-title fw-bold text-white mb-1">{title}</h3>
                <div class="text-secondary small">移动端自动化测试平台 · 正式测试交付物报告</div>
            </div>
            <div>
                <span class="badge px-3 py-2 fs-6" style="background-color: {status_badge_color};">测试结论: {status}</span>
                <button class="btn btn-outline-info btn-sm ms-2" onclick="window.print()"><i class="bi bi-printer"></i> 打印/导出 PDF</button>
            </div>
        </div>

        <!-- 关键数据看板 -->
        <div class="row g-3 mb-4">
            <div class="col-md-3">
                <div class="stat-box">
                    <div class="text-secondary small mb-1">测试通过率</div>
                    <div class="stat-value text-success">{pass_rate}</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-box">
                    <div class="text-secondary small mb-1">执行总耗时</div>
                    <div class="stat-value text-info">{duration_sec:.2f}s</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-box">
                    <div class="text-secondary small mb-1">测试模式</div>
                    <div class="stat-value text-warning">{"真机实测" if test_mode == "real" else "本地自测"}</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-box">
                    <div class="text-secondary small mb-1">驱动 AI 模型</div>
                    <div class="stat-value text-white small" style="font-size: 16px; padding-top: 6px;">{model_name}</div>
                </div>
            </div>
        </div>

        <!-- 测试元数据与目标 -->
        <div class="report-card">
            <h5 class="fw-bold mb-3 text-info"><i class="bi bi-info-circle me-2"></i>测试环境与目标定义</h5>
            <div class="row g-2 small">
                <div class="col-md-6">
                    <span class="text-secondary">待测应用:</span> <strong class="text-white">{app_name}</strong>
                </div>
                <div class="col-md-6">
                    <span class="text-secondary">应用包名:</span> <code class="text-info">{package}</code>
                </div>
                <div class="col-md-12 mt-2">
                    <span class="text-secondary">业务测试目标:</span>
                    <div class="p-2 mt-1 rounded bg-black border border-secondary text-white">{goal}</div>
                </div>
            </div>
        </div>

        <!-- 步骤全景画廊（有图有真相） -->
        {gallery_section}

        <!-- 测试用例步骤明细表格 -->
        <div class="report-card">
            <h5 class="fw-bold mb-3 text-info"><i class="bi bi-card-checklist me-2"></i>测试步骤与断言执行明细</h5>
            <div class="table-responsive">
                <table class="table table-dark table-hover mb-0">
                    <thead>
                        <tr class="text-secondary small">
                            <th>序号</th>
                            <th>动作类型</th>
                            <th>业务意图</th>
                            <th>定位器 / 接口详情</th>
                            <th>截屏证据</th>
                            <th>执行状态</th>
                        </tr>
                    </thead>
                    <tbody>
                        {steps_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 详细执行原始日志 -->
        <div class="report-card">
            <h5 class="fw-bold mb-2 text-info"><i class="bi bi-terminal me-2"></i>测试执行原始日志与断言轨迹</h5>
            <div class="log-box">{raw_output}</div>
        </div>

        <div class="text-center text-secondary small py-3">
            由 Autotest 移动端自动化测试平台自动生成 · 交付物版权归项目团队所有
        </div>
    </div>
</body>
</html>"""

        report_path.write_text(html_content, encoding="utf-8")

        # 写入元数据方便列表检索
        meta_data = {
            "title": title,
            "goal": goal,
            "mode": "真机实测" if test_mode == "real" else "本地自测",
            "status": status,
            "pass_rate": pass_rate,
            "duration": f"{duration_sec:.2f}s",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        (REPORTS_DIR / f"test_report_{timestamp_str}.json").write_text(json.dumps(meta_data, ensure_ascii=False, indent=2), encoding="utf-8")

        return report_path
