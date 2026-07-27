"""Scheduled audit report emails (HTML) with SMTP or local file fallback."""

from __future__ import annotations

import html
import logging
import os
import smtplib
import threading
import uuid
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from models import (
    get_report_subscription,
    insert_report_history,
    list_compliance,
    list_drift_marks,
    mark_subscription_sent,
    query_calls,
)

log = logging.getLogger("ata.report_mail")

DASHBOARD_URL = os.environ.get(
    "ATA_DASHBOARD_URL", "http://localhost:3002"
).rstrip("/")


def _reports_dir() -> Path:
    from paths import product_data_root

    return product_data_root(sub="reports")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def period_bounds(
    frequency: str, *, now: Optional[datetime] = None
) -> Tuple[datetime, datetime, datetime, datetime, str]:
    """Return (cur_from, cur_to, prev_from, prev_to, label)."""
    now = now or _utc_now()
    freq = (frequency or "weekly").lower()
    if freq == "daily":
        cur_to = now.replace(hour=0, minute=0, second=0, microsecond=0)
        cur_from = cur_to - timedelta(days=1)
        prev_to = cur_from
        prev_from = prev_to - timedelta(days=1)
        label = "昨日审计摘要"
    elif freq == "monthly":
        first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        cur_to = first
        # previous month start
        prev_month_last = first - timedelta(days=1)
        cur_from = prev_month_last.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_to = cur_from
        prev_last = cur_from - timedelta(days=1)
        prev_from = prev_last.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        label = "上月审计报告"
    else:  # weekly
        # Monday 00:00 as boundary; report covers previous Mon–Sun
        weekday = now.weekday()  # Mon=0
        this_monday = (now - timedelta(days=weekday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        cur_to = this_monday
        cur_from = this_monday - timedelta(days=7)
        prev_to = cur_from
        prev_from = prev_to - timedelta(days=7)
        label = "上周审计报告"
    return cur_from, cur_to, prev_from, prev_to, label


def _agg_calls(
    api_key: str, ts_from: str, ts_to: str, *, db_path=None
) -> Dict[str, Any]:
    rows = query_calls(
        api_key,
        ts_from=ts_from,
        ts_to=ts_to,
        limit=10000,
        db_path=db_path,
    )
    total_cost = sum(float(r.get("cost_usd") or 0) for r in rows)
    by_vendor: Dict[str, int] = {}
    for r in rows:
        v = (r.get("vendor") or "openai").lower()
        by_vendor[v] = by_vendor.get(v, 0) + 1
    return {
        "n": len(rows),
        "cost": round(total_cost, 6),
        "by_vendor": by_vendor,
        "rows": rows,
    }


def build_report_payload(
    *,
    api_key: str,
    frequency: str,
    content_options: Mapping[str, Any],
    db_path=None,
) -> Dict[str, Any]:
    cur_from, cur_to, prev_from, prev_to, label = period_bounds(frequency)
    cur = _agg_calls(api_key, _fmt(cur_from), _fmt(cur_to), db_path=db_path)
    prev = _agg_calls(api_key, _fmt(prev_from), _fmt(prev_to), db_path=db_path)

    cost_delta_pct = None
    if prev["cost"] > 0:
        cost_delta_pct = round((cur["cost"] - prev["cost"]) / prev["cost"] * 100.0, 1)
    elif cur["cost"] > 0:
        cost_delta_pct = 100.0

    pending = list_drift_marks(api_key, status="pending", limit=200, db_path=db_path)
    # new marks in period
    new_marks = [
        m
        for m in list_drift_marks(api_key, status=None, limit=500, db_path=db_path)
        if (m.get("timestamp") or "") >= _fmt(cur_from)
        and (m.get("timestamp") or "") < _fmt(cur_to)
    ]
    mark_types: Dict[str, int] = {}
    for m in new_marks:
        t = m.get("mark_type") or "unknown"
        mark_types[t] = mark_types.get(t, 0) + 1

    comps = list_compliance(api_key, limit=1, db_path=db_path)
    compliance_summary = {"pass": 0, "fail": 0, "manual": 0, "rate": None, "standard": None}
    if comps:
        import json

        summary = comps[0].get("summary") or {}
        if isinstance(summary, str):
            try:
                summary = json.loads(summary)
            except json.JSONDecodeError:
                summary = {}
        n_pass = int(summary.get("n_pass") or 0)
        n_fail = int(summary.get("n_fail") or 0)
        n_manual = int(summary.get("n_manual") or summary.get("n_review") or 0)
        total = n_pass + n_fail + n_manual
        compliance_summary = {
            "pass": n_pass,
            "fail": n_fail,
            "manual": n_manual,
            "rate": round(n_pass / total * 100.0, 1) if total else None,
            "standard": comps[0].get("standard_name") or comps[0].get("standard"),
        }

    vendor_share = []
    n = cur["n"] or 1
    for v, c in sorted(cur["by_vendor"].items(), key=lambda x: -x[1]):
        vendor_share.append({"vendor": v, "count": c, "pct": round(c / n * 100.0, 1)})

    return {
        "label": label,
        "frequency": frequency,
        "period_from": _fmt(cur_from),
        "period_to": _fmt(cur_to),
        "content_options": dict(content_options or {}),
        "overview": {
            "n_calls": cur["n"],
            "total_cost": cur["cost"],
            "pending_marks": len(pending),
            "compliance_rate": compliance_summary["rate"],
        },
        "cost_delta_pct": cost_delta_pct,
        "prev_cost": prev["cost"],
        "vendors": vendor_share,
        "new_marks": new_marks[:15],
        "mark_types": mark_types,
        "compliance": compliance_summary,
        "dashboard_url": DASHBOARD_URL,
    }


def render_report_html(payload: Mapping[str, Any]) -> str:
    opts = payload.get("content_options") or {}
    show_calls = opts.get("api_overview", True)
    show_marks = opts.get("drift_summary", True)
    show_comp = opts.get("compliance_summary", True)
    ov = payload.get("overview") or {}
    delta = payload.get("cost_delta_pct")
    if delta is None:
        delta_txt = "上期无费用基线"
    elif delta >= 0:
        delta_txt = f"本周期费用较上期增长 {delta}%"
    else:
        delta_txt = f"本周期费用较上期下降 {abs(delta)}%"

    sections: List[str] = []
    sections.append(
        f"""
        <h1 style="margin:0 0 8px;font-size:20px;color:#0b0f14">AI 行为审计 · {html.escape(str(payload.get('label')))}</h1>
        <p style="color:#556;font-size:13px;margin:0 0 16px">
          周期 {html.escape(str(payload.get('period_from'))[:10])}
          → {html.escape(str(payload.get('period_to'))[:10])}
        </p>
        <table style="width:100%;border-collapse:collapse;margin-bottom:18px">
          <tr>
            <td style="padding:10px;background:#f4f7fb;border-radius:6px">
              <div style="font-size:11px;color:#667">调用总数</div>
              <div style="font-size:22px;font-weight:600">{ov.get('n_calls', 0)}</div>
            </td>
            <td style="width:8px"></td>
            <td style="padding:10px;background:#f4f7fb">
              <div style="font-size:11px;color:#667">总费用</div>
              <div style="font-size:22px;font-weight:600">${float(ov.get('total_cost') or 0):.4f}</div>
            </td>
            <td style="width:8px"></td>
            <td style="padding:10px;background:#f4f7fb">
              <div style="font-size:11px;color:#667">待审计标记</div>
              <div style="font-size:22px;font-weight:600;color:#c0392b">{ov.get('pending_marks', 0)}</div>
            </td>
            <td style="width:8px"></td>
            <td style="padding:10px;background:#f4f7fb">
              <div style="font-size:11px;color:#667">合规通过率</div>
              <div style="font-size:22px;font-weight:600">
                {f"{ov.get('compliance_rate')}%" if ov.get('compliance_rate') is not None else "—"}
              </div>
            </td>
          </tr>
        </table>
        """
    )

    if show_calls:
        rows_v = "".join(
            f"<tr><td style='padding:6px 8px;border-bottom:1px solid #e8eef5'>{html.escape(v['vendor'])}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #e8eef5'>{v['count']}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #e8eef5'>{v['pct']}%</td></tr>"
            for v in (payload.get("vendors") or [])
        ) or "<tr><td colspan='3' style='padding:8px;color:#889'>无调用</td></tr>"
        sections.append(
            f"""
            <h2 style="font-size:15px;margin:0 0 8px">API 调用概览</h2>
            <p style="font-size:13px;color:#445">{html.escape(delta_txt)}</p>
            <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:16px">
              <thead><tr style="text-align:left;color:#667">
                <th style="padding:6px 8px">厂商</th><th>调用量</th><th>占比</th>
              </tr></thead>
              <tbody>{rows_v}</tbody>
            </table>
            """
        )

    if show_marks:
        types = payload.get("mark_types") or {}
        type_txt = ", ".join(f"{k}:{v}" for k, v in types.items()) or "无新增"
        mark_rows = ""
        for m in payload.get("new_marks") or []:
            dev = m.get("deviation")
            if isinstance(dev, dict):
                deg = html.escape(str(dev.get("severity") or dev.get("score") or dev)[:80])
            else:
                deg = html.escape(str(dev or "")[:80])
            mark_rows += (
                f"<tr><td style='padding:6px 8px;border-bottom:1px solid #e8eef5'>"
                f"{html.escape(str(m.get('mark_type') or ''))}</td>"
                f"<td style='padding:6px 8px;border-bottom:1px solid #e8eef5'>"
                f"{html.escape(str(m.get('call_endpoint') or '')[:60])}</td>"
                f"<td style='padding:6px 8px;border-bottom:1px solid #e8eef5'>{deg}</td></tr>"
            )
        if not mark_rows:
            mark_rows = "<tr><td colspan='3' style='padding:8px;color:#889'>本周期无新标记</td></tr>"
        sections.append(
            f"""
            <h2 style="font-size:15px;margin:0 0 8px">待审计标记摘要</h2>
            <p style="font-size:13px;color:#445">新增 {len(payload.get('new_marks') or [])} 条 · 类型分布：{html.escape(type_txt)}</p>
            <table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:16px">
              <thead><tr style="text-align:left;color:#667">
                <th style="padding:6px 8px">类型</th><th>端点</th><th>偏离</th>
              </tr></thead>
              <tbody>{mark_rows}</tbody>
            </table>
            """
        )

    if show_comp:
        c = payload.get("compliance") or {}
        sections.append(
            f"""
            <h2 style="font-size:15px;margin:0 0 8px">合规状态摘要</h2>
            <p style="font-size:13px;color:#445">
              标准：{html.escape(str(c.get('standard') or '尚未检查'))}<br/>
              通过 {c.get('pass', 0)} · 未通过 {c.get('fail', 0)} · 需人工审查 {c.get('manual', 0)}
              · 通过率 {f"{c.get('rate')}%" if c.get('rate') is not None else "—"}
            </p>
            """
        )

    dash = html.escape(str(payload.get("dashboard_url") or DASHBOARD_URL))
    sections.append(
        f"""
        <p style="margin-top:20px">
          <a href="{dash}" style="background:#1a3d2c;color:#3dd68c;padding:10px 16px;
             text-decoration:none;border-radius:4px;font-size:13px">查看完整仪表盘</a>
        </p>
        <p style="color:#99a;font-size:11px;margin-top:24px">
          ai-attestation · MVP · 本邮件为自动审计摘要
        </p>
        """
    )

    body = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>ai-attestation Report</title></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;
 background:#eef2f6;padding:24px">
  <div style="max-width:640px;margin:0 auto;background:#fff;padding:24px;border-radius:8px;
   border:1px solid #dbe3ec">{body}</div>
</body></html>"""


def _smtp_configured() -> bool:
    return bool(os.environ.get("ATA_SMTP_HOST") and os.environ.get("ATA_SMTP_FROM"))


def deliver_html(
    *,
    to_emails: List[str],
    subject: str,
    html_body: str,
) -> Tuple[str, Optional[str]]:
    """Send via SMTP or write to reports/. Returns (status, error_or_path)."""
    if _smtp_configured():
        host = os.environ["ATA_SMTP_HOST"]
        port = int(os.environ.get("ATA_SMTP_PORT", "587"))
        user = os.environ.get("ATA_SMTP_USER", "")
        password = os.environ.get("ATA_SMTP_PASSWORD", "")
        from_addr = os.environ["ATA_SMTP_FROM"]
        use_tls = os.environ.get("ATA_SMTP_TLS", "1") not in ("0", "false", "False")
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = ", ".join(to_emails)
            msg.attach(MIMEText(html_body, "html", "utf-8"))
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                if use_tls:
                    smtp.starttls()
                if user:
                    smtp.login(user, password)
                smtp.sendmail(from_addr, to_emails, msg.as_string())
            return "success", None
        except Exception as e:
            return "failed", str(e)

    path = _reports_dir() / f"email_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.html"
    path.write_text(html_body, encoding="utf-8")
    log.info("SMTP not configured; wrote report to %s", path)
    return "success", str(path)


def parse_emails(raw: str) -> List[str]:
    parts = [p.strip() for p in (raw or "").replace(";", ",").split(",")]
    return [p for p in parts if p and "@" in p]


def send_subscription_report(
    *,
    subscription_id: str,
    db_path=None,
    test: bool = False,
) -> Dict[str, Any]:
    sub = get_report_subscription(subscription_id, db_path=db_path)
    if not sub:
        return {"ok": False, "error": "subscription not found"}
    emails = parse_emails(sub.get("email") or "")
    if not emails:
        return {"ok": False, "error": "no valid email"}
    opts = sub.get("content_options") or {}
    payload = build_report_payload(
        api_key=sub["api_key"],
        frequency=sub.get("frequency") or "weekly",
        content_options=opts,
        db_path=db_path,
    )
    if test:
        payload = {**payload, "label": f"[测试] {payload.get('label')}"}
    html_body = render_report_html(payload)
    subject = f"[ai-attestation] {payload.get('label')}"
    status, err = deliver_html(to_emails=emails, subject=subject, html_body=html_body)
    sent_at = _fmt(_utc_now())
    hist_id = f"rh_{uuid.uuid4().hex[:16]}"
    insert_report_history(
        {
            "id": hist_id,
            "subscription_id": subscription_id,
            "sent_at": sent_at,
            "status": status,
            "error_message": err if status == "failed" else (
                f"written:{err}" if err and status == "success" else None
            ),
        },
        db_path=db_path,
    )
    if status == "success" and not test:
        mark_subscription_sent(subscription_id, sent_at=sent_at, db_path=db_path)
    return {
        "ok": status == "success",
        "status": status,
        "history_id": hist_id,
        "error": err if status == "failed" else None,
        "log_path": err if status == "success" and err and str(err).endswith(".html") else None,
        "payload_summary": {
            "n_calls": payload["overview"]["n_calls"],
            "total_cost": payload["overview"]["total_cost"],
        },
    }


def send_subscription_async(
    *,
    subscription_id: str,
    db_path=None,
    test: bool = False,
) -> None:
    def _run() -> None:
        try:
            send_subscription_report(
                subscription_id=subscription_id, db_path=db_path, test=test
            )
        except Exception:
            log.exception("async report send failed")

    threading.Thread(target=_run, name="ata-report-mail", daemon=True).start()


def subscription_due(sub: Mapping[str, Any], *, now: Optional[datetime] = None) -> bool:
    now = now or _utc_now()
    last = sub.get("last_sent_at")
    freq = (sub.get("frequency") or "weekly").lower()
    if not last:
        # first send: daily after 06:00 UTC, weekly on Monday, monthly on day 1
        if freq == "daily":
            return now.hour >= 6
        if freq == "monthly":
            return now.day == 1 and now.hour >= 6
        return now.weekday() == 0 and now.hour >= 6
    try:
        last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
    except ValueError:
        return True
    if freq == "daily":
        return (now - last_dt) >= timedelta(hours=23) and now.hour >= 6
    if freq == "monthly":
        return now.day == 1 and now.hour >= 6 and (now - last_dt) >= timedelta(days=20)
    # weekly Monday
    return (
        now.weekday() == 0
        and now.hour >= 6
        and (now - last_dt) >= timedelta(days=6)
    )


_scheduler_started = False


def start_report_scheduler(*, db_path=None) -> None:
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    def _loop() -> None:
        import time

        from models import list_report_subscriptions

        while True:
            try:
                for sub in list_report_subscriptions(db_path=db_path):
                    if subscription_due(sub):
                        send_subscription_report(
                            subscription_id=sub["id"], db_path=db_path, test=False
                        )
            except Exception:
                log.exception("report scheduler tick failed")
            time.sleep(3600)

    threading.Thread(target=_loop, name="ata-report-scheduler", daemon=True).start()
