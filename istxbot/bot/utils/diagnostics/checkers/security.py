"""
فاحص الأمان — أسرار مكشوفة، SQL injection، subprocess خطر، ثغرات شائعة
"""
import re
from pathlib import Path
from typing import Optional

from ..models import Issue, Severity

PROJECT_ROOT = Path("/home/ngm/istxbot")

# كلمات مفتاحية خطيرة للبحث عنها
DANGER_PATTERNS = [
    # SQL injection risk
    (r"execute\s*\(\s*f['\"]", Severity.HIGH,
     "SQL injection محتمل: استخدام f-string في استعلام SQL",
     "استخدم parameterized queries (? placeholders) بدلاً من تضمين القيم مباشرة."),
    # subprocess shell=True
    (r"subprocess\.\w+\s*\([^)]*shell\s*=\s*True", Severity.HIGH,
     "استخدام shell=True في subprocess",
     "تجنب shell=True. استخدم قائمة arguments مباشرة: subprocess.run(['cmd', 'arg1'])."),
    # sudo بدون تقييد
    (r"sudo\s+(?!systemctl\s+(?:start|stop|restart|status))", Severity.MEDIUM,
     "استخدام sudo غير مقيد في الكود",
     "قيد sudo بالأوامر المحددة فقط عبر /etc/sudoers لتجنب تصعيد الصلاحيات."),
    # shell scripts: hardcoded tokens
    (r"""export\s+(\w*(?:TOKEN|SECRET|PASSWORD|KEY)\w*)\s*=\s*['"]([^'"]{8,})['"]""", Severity.CRITICAL,
     "توكن مكشوف في shell script",
     "انقل التوكن لملف .env واستخدم source .env بدلاً من تضمينه مباشرة."),
]

# ملفات يجب تجاهلها
IGNORED_DIRS = {"__pycache__", "node_modules", ".git", ".gradle", "build", "dist", ".claude", "diagnostics"}


def check_security(project_root: Optional[Path] = None) -> list[Issue]:
    """فاحص الأمان الرئيسي"""
    issues: list[Issue] = []
    root = project_root or PROJECT_ROOT

    checkable_files: list[Path] = []
    for ext in [".py", ".sh", ".js", ".jsx", ".php"]:
        for f in root.rglob(f"*{ext}"):
            if any(ignored in f.parts for ignored in IGNORED_DIRS):
                continue
            if f.stat().st_size > 200_000:
                continue
            checkable_files.append(f)

    for file_path in checkable_files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        rel_path = str(file_path.relative_to(root))

        for pattern, severity, title, solution in DANGER_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE):
                line_no = content[:match.start()].count("\n") + 1
                snippet = match.group(0)[:80]

                # فلترة false positives
                if "os.getenv" in content[max(0, match.start()-100):match.start()]:
                    continue
                if "changeme" in snippet.lower() or "xxx" in snippet.lower():
                    continue
                if "your-" in snippet.lower() or "your_" in snippet.lower() or "your " in snippet.lower():
                    continue

                issues.append(Issue(
                    severity=severity,
                    category="security",
                    title=title,
                    solution=solution,
                    file_path=rel_path,
                    line_number=line_no,
                    code_snippet=snippet,
                ))

    # ═══ فحص .env في .gitignore ═══

    gitignore_path = root / ".gitignore"
    if gitignore_path.exists():
        gitignore_content = gitignore_path.read_text(encoding="utf-8")
        required_patterns = {
            ".env": "ملفات البيئة",
            "*.db": "ملفات قاعدة البيانات",
            "service-account.json": "ملفات حسابات الخدمة",
        }
        for pattern, desc in required_patterns.items():
            if pattern not in gitignore_content:
                issues.append(Issue(
                    severity=Severity.HIGH,
                    category="security",
                    title=f"{desc} ({pattern}) غير مضافة لـ .gitignore",
                    solution=f"أضف '{pattern}' لملف .gitignore لمنع تسريب البيانات الحساسة للمستودع.",
                    file_path=".gitignore",
                ))

    return issues
