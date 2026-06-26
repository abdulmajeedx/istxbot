"""
فاحص الإعدادات — متغيرات بيئة مطلوبة، خدمات systemd، ملفات تهيئة
"""

import subprocess
from pathlib import Path
from typing import Optional

from ..models import Issue, Severity

PROJECT_ROOT = Path("/home/ngm/istxbot")
BOT_DOWNLOAD_DIR = Path("/home/ngm/bot_download_telegram")

# متغيرات البيئة المطلوبة لكل مكون
REQUIRED_ENV_VARS = {
    "البوت الرئيسي": [
        "BOT_TOKEN",
        "ADMIN_ID",
    ],
    "تطبيق الويب": [
        "BOT_TOKEN",
        "ADMIN_ID",
        "ADMIN_PASSWORD_HASH",
        "DB_PATH",
    ],
    "البوت التطويري": [
        "DEV_BOT_TOKEN",
        "DEEPSEEK_API_KEY",
        "ADMIN_CHAT_ID",
    ],
}

# خدمات systemd المتوقعة
EXPECTED_SERVICES = [
    ("telegram-bot.service", "البوت الرئيسي"),
    ("admin-istx.service", "لوحة إدارة الويب"),
    ("dev-bot.service", "بوت التطوير"),
    ("monitor.service", "لوحة المراقبة"),
]


def _check_env_file(env_path: Path) -> dict[str, bool]:
    """فحص وجود متغيرات البيئة في ملف .env"""
    if not env_path.exists():
        return {}
    try:
        content = env_path.read_text(encoding="utf-8")
    except Exception:
        return {}
    found = {}
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        found[key] = True
    return found


def _check_systemd_service(service_name: str) -> tuple[bool, str]:
    """التحقق من حالة خدمة systemd"""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, "unknown"


def check_config(project_root: Optional[Path] = None) -> list[Issue]:
    """فاحص الإعدادات الرئيسي"""
    issues: list[Issue] = []
    root = project_root or PROJECT_ROOT

    # ═══ متغيرات البيئة ═══

    env_file = root / "istxbot" / ".env"
    env_vars_found = _check_env_file(env_file)

    # أيضاً افحص .env في bot_download_telegram إن وجد
    if BOT_DOWNLOAD_DIR.exists():
        bot_env_vars = _check_env_file(BOT_DOWNLOAD_DIR / ".env")
        env_vars_found.update(bot_env_vars)

    for component, vars_needed in REQUIRED_ENV_VARS.items():
        missing = [v for v in vars_needed if not env_vars_found.get(v)]
        if missing:
            issues.append(Issue(
                severity=Severity.HIGH,
                category="config",
                title=f"متغيرات بيئة مفقودة لـ {component}: {', '.join(missing)}",
                solution=f"أضف المتغيرات المفقودة لملف .env في المسار المناسب: {env_file}",
                file_path=str(env_file.relative_to(root)) if env_file.exists() else "istxbot/.env",
            ))

    # ═══ ملف .env غير موجود ═══

    if not env_file.exists():
        issues.append(Issue(
            severity=Severity.CRITICAL,
            category="config",
            title="ملف .env غير موجود",
            solution="أنشئ ملف .env في istxbot/ يحتوي على المتغيرات المطلوبة (BOT_TOKEN, ADMIN_ID, إلخ).",
            file_path="istxbot/.env",
        ))

    # ═══ خدمات systemd ═══

    for service_name, label in EXPECTED_SERVICES:
        is_active, status = _check_systemd_service(service_name)
        if not is_active:
            # لا نبلغ عن الخدمات غير الموجودة في بيئة التطوير
            if status == "unknown":
                continue
            severity = Severity.CRITICAL if service_name == "telegram-bot.service" else Severity.MEDIUM
            issues.append(Issue(
                severity=severity,
                category="config",
                title=f"خدمة {label} ({service_name}) غير نشطة: {status}",
                solution=f"شغّل الخدمة: sudo systemctl start {service_name} "
                         f"أو تحقق من السجلات: journalctl -u {service_name} -n 50",
                file_path=f"/etc/systemd/system/{service_name}",
            ))

    # ═══ ملفات تهيئة nginx ═══

    nginx_dir = root / "nginx"
    if nginx_dir.exists() and not list(nginx_dir.iterdir()):
        issues.append(Issue(
            severity=Severity.MEDIUM,
            category="config",
            title="مجلد nginx/ فارغ - إعدادات nginx مفقودة",
            solution="أضف ملفات تهيئة nginx للمواقع (virtual hosts) في مجلد nginx/.",
            file_path="nginx/",
        ))

    return issues

