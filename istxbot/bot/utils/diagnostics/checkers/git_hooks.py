"""
فاحص Git — ملفات غير متتبعة مهمة، فروع قديمة، حالة المستودع
"""
import subprocess
from pathlib import Path
from typing import Optional

from ..models import Issue, Severity

PROJECT_ROOT = Path("/home/ngm/istxbot")


def _run_git(args: list[str], cwd: Path) -> tuple[bool, str]:
    """تشغيل أمر git وإرجاع النتيجة"""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, ""


def check_git(project_root: Optional[Path] = None) -> list[Issue]:
    """فاحص Git الرئيسي"""
    issues: list[Issue] = []
    root = project_root or PROJECT_ROOT

    # ═══ ملفات غير متتبعة مهمة ═══

    ok, output = _run_git(["status", "--short"], root)
    if ok:
        for line in output.split("\n"):
            if not line.strip():
                continue
            status = line[:2].strip()
            filepath = line[3:].strip()

            # ملفات غير متتبعة
            if status == "??":
                # تجاهل ملفات معينة
                if any(filepath.endswith(ext) for ext in [".db", ".db-journal", ".db-wal", ".db-shm"]):
                    continue
                if "__pycache__" in filepath:
                    continue
                if filepath.endswith(".pyc"):
                    continue

                # تنبيه للملفات المهمة غير المتتبعة
                if any(filepath.endswith(ext) for ext in [".py", ".jsx", ".js", ".kt", ".php"]):
                    issues.append(Issue(
                        severity=Severity.MEDIUM,
                        category="git",
                        title=f"ملف كود غير متتبع: {filepath}",
                        solution=f"أضف الملف للتتبع: git add {filepath}",
                        file_path=filepath,
                    ))

            # ملفات معدلة
            if status == "M ":
                issues.append(Issue(
                    severity=Severity.INFO,
                    category="git",
                    title=f"ملف معدل غير مرفوع: {filepath}",
                    solution="ارفع التغييرات أو ناقشها: git add ثم git commit.",
                    file_path=filepath,
                ))

            # ملفات محذوفة
            if status == "D ":
                issues.append(Issue(
                    severity=Severity.INFO,
                    category="git",
                    title=f"ملف محذوف غير مرحل: {filepath}",
                    solution="إذا كان الحذف مقصوداً: git add -u ثم git commit.",
                    file_path=filepath,
                ))

    # ═══ فحص اتصال المستودع البعيد ═══

    ok, remotes = _run_git(["remote", "-v"], root)
    if not ok or not remotes:
        issues.append(Issue(
            severity=Severity.HIGH,
            category="git",
            title="لا يوجد مستودع بعيد (remote) مرتبط",
            solution="اربط المستودع بمستودع بعيد: git remote add origin <url>",
            file_path=".git/config",
        ))

    # ═══ فحص فروع قديمة ═══

    ok, branches = _run_git(["branch", "--format=%(refname:short)|%(committerdate:iso)"], root)
    if ok:
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=30)
        for line in branches.split("\n"):
            if "|" not in line:
                continue
            branch, date_str = line.split("|", 1)
            if branch.strip() == "main" or branch.strip() == "master":
                continue
            try:
                branch_date = datetime.fromisoformat(date_str.strip())
                if branch_date < cutoff:
                    issues.append(Issue(
                        severity=Severity.INFO,
                        category="git",
                        title=f"فرع قديم: {branch.strip()} (آخر نشاط: {branch_date.strftime('%Y-%m-%d')})",
                        solution=f"إذا تم دمج الفرع: git branch -d {branch.strip()}. إذا لم يكتمل العمل فيه، استكمله أو احذفه.",
                        file_path=f"branch: {branch.strip()}",
                    ))
            except ValueError:
                pass

    return issues
