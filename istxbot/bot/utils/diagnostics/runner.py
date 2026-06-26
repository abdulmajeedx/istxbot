"""
منسق الفحص الرئيسي — يجمع نتائج جميع الفاحصين ويرسل التقرير
"""
import os

import time
import logging
from pathlib import Path

from typing import Optional

from .models import Issue, Report, Severity
from .checkers import ALL_CHECKERS
from .checkers.api_mismatch import PROJECT_ROOT

logger = logging.getLogger("istxbot-check")

# ═══ إرسال تيليجرام ═══

def _send_telegram(text: str, bot_token: str = None, admin_id: str = None) -> bool:
    """إرسال رسالة نصية عبر تيليجرام (نمط HTTP POST المباشر)"""
    token = bot_token or os.getenv("BOT_TOKEN", "")
    chat_id = admin_id or os.getenv("ADMIN_ID", "")

    if not token or not chat_id:
        logger.warning("Telegram notification skipped: BOT_TOKEN or ADMIN_ID not set")
        return False

    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"

        # تقسيم الرسائل الطويلة (> 4000 حرف)
        chunks = []
        current_chunk = ""
        for line in text.split("\n"):
            if len(current_chunk) + len(line) + 1 > 3900:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += "\n" + line if current_chunk else line
        if current_chunk:
            chunks.append(current_chunk)

        for i, chunk in enumerate(chunks):
            prefix = f"({i+1}/{len(chunks)}) " if len(chunks) > 1 else ""
            resp = requests.post(url, json={
                "chat_id": int(chat_id),
                "text": prefix + chunk,
                "parse_mode": "HTML",
            }, timeout=10)
            if resp.status_code != 200:
                logger.error(f"Telegram send failed: {resp.status_code} {resp.text}")
                return False

        logger.info(f"Telegram notification sent ({len(chunks)} chunk(s))")
        return True
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


def _format_report(report: Report, max_issues_per_category: int = 8) -> str:
    """تنسيق التقرير كنص HTML منسق للإرسال عبر تيليجرام"""
    sev = report.by_severity
    cat = report.by_category

    lines = [
        "🩺 <b>تقرير صحة المشروع — istxbot-check</b>",
        f"📅 {report.timestamp.strftime('%Y-%m-%d %H:%M')}",
        "",
        f"📊 <b>{report.summary}</b>",
        "",
    ]

    # جدول الخطورة
    lines.append("🔻 <b>حسب الخطورة:</b>")
    for s in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
        if sev[s]:
            lines.append(f"  {s.value} {s.label_ar}: {sev[s]}")

    lines.append("")
    lines.append("📂 <b>حسب الفئة:</b>")
    for category, count in sorted(cat.items()):
        lines.append(f"  • {category}: {count}")

    lines.append("")
    lines.append("━" * 30)
    lines.append("")

    # تفاصيل المشاكل — الحرجة أولاً
    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
        sev_issues = [i for i in report.issues if i.severity == severity]
        if not sev_issues:
            continue

        lines.append(f"{severity.value} <b>{severity.label_ar} ({len(sev_issues)})</b>")
        lines.append("")

        for issue in sev_issues[:max_issues_per_category]:
            line_info = f":{issue.line_number}" if issue.line_number else ""
            lines.append(issue.telegram_line())

        if len(sev_issues) > max_issues_per_category:
            lines.append(f"  ... و {len(sev_issues) - max_issues_per_category} مشكلة أخرى")

    return "\n".join(lines)


def _format_console_report(report: Report) -> str:
    """تنسيق التقرير للطرفية (console) مع ألوان"""
    # ANSI color codes
    C = {
        "red": "\033[91m", "yellow": "\033[93m", "green": "\033[92m",
        "blue": "\033[94m", "cyan": "\033[96m", "reset": "\033[0m",
        "bold": "\033[1m",
    }

    sev = report.by_severity
    lines = [
        f"{C['bold']}{C['cyan']}╔══════════════════════════════════════════════╗{C['reset']}",
        f"{C['bold']}{C['cyan']}║   🩺  تقرير صحة المشروع — istxbot-check     ║{C['reset']}",
        f"{C['bold']}{C['cyan']}╚══════════════════════════════════════════════╝{C['reset']}",
        f"📅 {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"{C['bold']}📊 {report.summary}{C['reset']}",
        "",
    ]

    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
        sev_issues = [i for i in report.issues if i.severity == severity]
        if not sev_issues:
            continue

        color = {
            Severity.CRITICAL: C["red"],
            Severity.HIGH: C["yellow"],
            Severity.MEDIUM: C["yellow"],
            Severity.LOW: C["blue"],
            Severity.INFO: C["reset"],
        }[severity]

        lines.append(f"{color}{C['bold']}{severity.value} {severity.label_ar} ({len(sev_issues)}){C['reset']}")
        for issue in sev_issues:
            lines.append(str(issue))
        lines.append("")

    return "\n".join(lines)


def run_all_checks(
    checks: Optional[list[str]] = None,
    project_root: Optional[Path] = None,
    notify: bool = False,
    output_json: Optional[str] = None,
    auto_fix: bool = False,
) -> Report:
    """
    تشغيل جميع الفاحصين وإرجاع تقرير مجمع

    Args:
        checks: قائمة الفاحصين المراد تشغيلهم (None = الكل)
        project_root: جذر المشروع
        notify: إرسال إشعار تيليجرام
        output_json: مسار لحفظ التقرير كـ JSON
        auto_fix: تطبيق الإصلاحات التلقائية للمشاكل القابلة للإصلاح

    Returns:
        تقرير مجمع
    """
    root = project_root or PROJECT_ROOT
    report = Report()

    logger.info("Starting project health check...")
    start_time = time.time()

    for check_id, check_fn, check_label in ALL_CHECKERS:
        if checks is not None and check_id not in checks:
            continue
        try:
            logger.info(f"  Running: {check_label} ({check_id})...")
            check_start = time.time()
            issues = check_fn(root)
            elapsed = time.time() - check_start
            report.issues.extend(issues)
            logger.info(f"    Found {len(issues)} issue(s) in {elapsed:.1f}s")
        except Exception as e:
            logger.error(f"    Check '{check_id}' failed: {e}")
            report.issues.append(Issue(
                severity=Severity.HIGH,
                category="system",
                title=f"فشل فاحص {check_label}",
                solution=f"حدث خطأ أثناء تشغيل الفاحص: {str(e)[:100]}. راجع السجلات.",
                file_path=f"diagnostics/checkers/{check_id}.py",
            ))

    total_time = time.time() - start_time
    logger.info(f"Health check complete in {total_time:.1f}s: {report.total_issues} issue(s) found")

    # ترتيب النتائج: الحرجة أولاً
    sev_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}
    report.issues.sort(key=lambda i: sev_order.get(i.severity, 99))

    # ═══ الإصلاح التلقائي ═══
    fixed_count = 0
    if auto_fix:
        from .auto_fix import find_fix
        logger.info("Applying auto-fixes...")
        issues_to_remove = []
        for issue in report.issues:
            fix_func = find_fix(issue)
            if fix_func:
                try:
                    if fix_func(issue, root):
                        fixed_count += 1
                        issues_to_remove.append(issue)
                        logger.info(f"  ✅ Fixed: {issue.title[:60]}...")
                except Exception as e:
                    logger.error(f"  ❌ Fix failed: {issue.title[:40]}... ({e})")

        # إزالة المشاكل التي تم إصلاحها من التقرير
        for issue in issues_to_remove:
            report.issues.remove(issue)
        logger.info(f"Auto-fix: {fixed_count} issue(s) resolved")

    # إخراج للطرفية
    if not output_json:
        print(_format_console_report(report))
        print(f"⏱️  اكتمل الفحص في {total_time:.1f} ثانية")
        if fixed_count:
            print(f"🔧 تم إصلاح {fixed_count} مشكلة تلقائياً")

    # حفظ JSON
    if output_json:
        import json

        output_path = Path(output_json)
        output_path.write_text(
            json.dumps({
                "timestamp": report.timestamp.isoformat(),
                "total_issues": report.total_issues,
                "by_severity": {s.label_ar: c for s, c in report.by_severity.items()},
                "issues": [
                    {
                        "severity": i.severity.label_ar,
                        "category": i.category,
                        "title": i.title,
                        "solution": i.solution,
                        "file_path": i.file_path,
                        "line_number": i.line_number,
                    }
                    for i in report.issues
                ],
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"Report saved to {output_path}")

    # إرسال تيليجرام
    if notify:
        telegram_text = _format_report(report)
        if _send_telegram(telegram_text):
            print("✅ تم إرسال التقرير عبر تيليجرام")
        else:
            print("⚠️  فشل إرسال تيليجرام (تأكد من BOT_TOKEN و ADMIN_ID)")

    return report


