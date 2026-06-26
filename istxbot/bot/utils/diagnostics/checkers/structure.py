"""
فاحص الهيكلة — ملفات كبيرة، روابط رمزية مكسورة، مجلدات فارغة
"""
import os
from pathlib import Path
from typing import Optional

from ..models import Issue, Severity

PROJECT_ROOT = Path("/home/ngm/istxbot")

# الحد الأقصى لعدد الأسطر قبل التنبيه
MAX_FILE_LINES = 500
# المجلدات التي يتم تجاهلها تماماً
IGNORED_DIRS = {
    "__pycache__", "node_modules", ".git", ".gradle", "build",
    "dist", ".claude", "downloads", "data", "logs", ".venv", "venv",
}
# امتدادات الملفات التي يتم فحصها
CHECKED_EXTENSIONS = {".py", ".js", ".jsx", ".kt", ".php", ".css", ".sh"}


def check_structure(project_root: Optional[Path] = None) -> list[Issue]:
    """فاحص الهيكلة الرئيسي"""
    issues: list[Issue] = []
    root = project_root or PROJECT_ROOT

    # ═══ ملفات كبيرة ═══

    for file_path in root.rglob("*"):
        if file_path.is_dir():
            continue
        if any(ignored in file_path.parts for ignored in IGNORED_DIRS):
            continue
        if file_path.suffix not in CHECKED_EXTENSIONS:
            continue

        try:
            line_count = sum(1 for _ in open(file_path, encoding="utf-8", errors="ignore"))
        except Exception:
            continue

        if line_count > MAX_FILE_LINES:
            rel_path = str(file_path.relative_to(root))
            severity = Severity.CRITICAL if line_count > 1500 else (
                Severity.HIGH if line_count > 1000 else Severity.MEDIUM
            )

            # اقتراح التقسيم
            if file_path.suffix == ".py":
                solution = (
                    f"قسّم هذا الملف ({line_count} سطر) إلى وحدات أصغر. "
                    f"لـ Python: استخدم حزمة (package) مع __init__.py وفصل المنطق إلى modules. "
                    f"لـ Flask: استخدم Blueprints لتقسيم المسارات."
                )
            elif file_path.suffix in (".jsx", ".js"):
                solution = (
                    f"قسّم هذا الملف ({line_count} سطر) إلى مكونات أصغر. "
                    f"انقل الدوال المساعدة لملف utils منفصل، والأنماط لملف CSS."
                )
            else:
                solution = f"هذا الملف كبير جداً ({line_count} سطر). قسّمه إلى ملفات أصغر للصيانة."

            issues.append(Issue(
                severity=severity,
                category="structure",
                title=f"ملف كبير جداً: {rel_path} ({line_count} سطر)",
                solution=solution,
                file_path=rel_path,
            ))

    # ═══ روابط رمزية مكسورة ═══

    for file_path in root.rglob("*"):
        if any(ignored in file_path.parts for ignored in IGNORED_DIRS):
            continue
        if file_path.is_symlink():
            try:
                target = file_path.resolve(strict=True)
            except (FileNotFoundError, OSError):
                rel_path = str(file_path.relative_to(root))
                link_target = os.readlink(str(file_path))
                issues.append(Issue(
                    severity=Severity.CRITICAL,
                    category="structure",
                    title=f"رابط رمزي مكسور: {rel_path}",
                    solution=f"الرابط يشير إلى {link_target} (غير موجود). احذف الرابط وأنشئ الملف الفعلي، أو صحح الهدف.",
                    file_path=rel_path,
                ))

    # ═══ مجلدات فارغة ═══

    for dir_path in root.rglob("*"):
        if not dir_path.is_dir():
            continue
        if any(ignored in dir_path.parts for ignored in IGNORED_DIRS):
            continue
        # تجاهل المجلدات التي تحوي .gitkeep
        if list(dir_path.glob(".gitkeep")):
            continue
        try:
            contents = list(dir_path.iterdir())
        except PermissionError:
            continue
        if not contents:
            rel_path = str(dir_path.relative_to(root))
            issues.append(Issue(
                severity=Severity.LOW,
                category="structure",
                title=f"مجلد فارغ: {rel_path}/",
                solution="احذف المجلد الفارغ أو أضف ملف .gitkeep إذا كان مطلوباً للهيكلة.",
                file_path=rel_path + "/",
            ))

    return issues
