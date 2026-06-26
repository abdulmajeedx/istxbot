#!/usr/bin/env python3
"""
🩺 istxbot-check — أداة فحص صحة المشروع الشاملة

الاستخدام:
    python3 scripts/istxbot_check.py              # فحص كامل للطرفية
    python3 scripts/istxbot_check.py --notify     # فحص + إرسال لتلجرام
    python3 scripts/istxbot_check.py --check api,security   # فحص محدد
    python3 scripts/istxbot_check.py --quiet --output report.json  # حفظ للملف
    python3 scripts/istxbot_check.py --help       # عرض المساعدة
"""
import os
import sys
import argparse
import logging
from pathlib import Path

# إضافة المسار للـ PYTHONPATH
# هيكلة المشروع: <repo>/istxbot/ يحتوي على bot/, web/, config/ (حزمة Python)
REPO_ROOT = Path(__file__).parent.parent  # /home/ngm/istxbot
PROJECT_ROOT = REPO_ROOT
sys.path.insert(0, str(REPO_ROOT / "istxbot"))  # /home/ngm/istxbot/istxbot → bot, web, config
sys.path.insert(0, str(REPO_ROOT))  # للوصول لـ admin-panel, dev-bot إلخ

# إعداد logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-7s %(message)s",
)
logger = logging.getLogger("istxbot-check")

# تحميل متغيرات البيئة إن وجدت
try:
    from dotenv import load_dotenv
    env_path = REPO_ROOT / "istxbot" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass


def main():
    parser = argparse.ArgumentParser(
        description="🩺 istxbot-check — فحص صحة المشروع",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
أمثلة:
  %(prog)s                        فحص كامل للطرفية
  %(prog)s --notify               فحص وإرسال إشعار تيليجرام
  %(prog)s --check api,security   فحص API والأمان فقط
  %(prog)s --quiet -o report.json فحص صامت وحفظ النتائج
        """,
    )
    parser.add_argument(
        "--check", "-c",
        type=str,
        help="الفاحصين المراد تشغيلهم (مفصولة بفواصل): api,code_quality,structure,security,git,config",
    )
    parser.add_argument(
        "--notify", "-n",
        action="store_true",
        help="إرسال التقرير عبر تيليجرام",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="حفظ التقرير كملف JSON",
    )
    parser.add_argument(
        "--fix", "-f",
        action="store_true",
        help="تطبيق الإصلاحات التلقائية على المشاكل القابلة للحل",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="عدم طباعة التقرير في الطرفية",
    )
    parser.add_argument(
        "--root", "-r",
        type=str,
        default=str(PROJECT_ROOT),
        help="جذر المشروع (افتراضي: المسار الحالي)",
    )

    args = parser.parse_args()

    # تجهيز قائمة الفاحصين
    checks = None
    if args.check:
        checks = [c.strip() for c in args.check.split(",")]
        valid = {"api", "code_quality", "structure", "security", "git", "config"}
        invalid = set(checks) - valid
        if invalid:
            print(f"❌ فاحصين غير معروفين: {', '.join(invalid)}")
            print(f"   المتاح: {', '.join(sorted(valid))}")
            sys.exit(1)

    # تعطيل الطباعة في الوضع الهادئ
    if args.quiet:
        import io
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

    # تشغيل الفحص
    from bot.utils.diagnostics.runner import run_all_checks

    try:
        report = run_all_checks(
            checks=checks,
            project_root=Path(args.root),
            notify=args.notify,
            output_json=args.output,
            auto_fix=args.fix,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        sys.exit(1)

    # استعادة stdout في الوضع الهادئ
    if args.quiet:
        sys.stdout = old_stdout
        if args.output:
            print(f"✅ تم حفظ التقرير: {args.output}")
            print(f"   {report.summary}")

    # كود الخروج بناءً على النتائج
    from bot.utils.diagnostics.models import Severity as Sev
    if report.by_severity[Sev.CRITICAL] > 0:
        sys.exit(2)  # مشاكل حرجة
    elif report.total_issues > 0:
        sys.exit(1)  # توجد مشاكل
    else:
        sys.exit(0)  # نظيف


if __name__ == "__main__":
    main()
