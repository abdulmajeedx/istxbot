"""
نظام الإصلاح التلقائي — يطبق حلولاً آلية للمشاكل المكتشفة
كل دالة إصلاح ترجع True إذا نجح الإصلاح
"""
import re
import os
from pathlib import Path
from typing import Optional

from .models import Issue, Severity  # noqa

PROJECT_ROOT= Path("/home/ngm/istxbot")


# ═══ مسجّل الإصلاحات ═══

FIX_REGISTRY: dict[str, callable] = {}
"""قاموس يربط أنماط عناوين المشاكل بدوال الإصلاح"""


def register_fix(title_pattern: str):
    """Decorator لتسجيل دالة إصلاح مع نمط عنوان"""
    def decorator(func):
        FIX_REGISTRY[title_pattern] = func
        return func
    return decorator


# ملفات محمية — لا يمكن إصلاحها تلقائياً (تحتوي imports معقدة متعددة الأسطر)
PROTECTED_FILES = {
    "istxbot/web/routes/public.py",
    "istxbot/web/routes/admin.py",
    "istxbot/web/routes/admin_bot.py",
    "istxbot/web/common.py",
    "istxbot/web/app.py",
}


def find_fix(issue: Issue) -> Optional[callable]:
    """البحث عن دالة إصلاح مناسبة لمشكلة معينة"""
    # لا تلمس الملفات المحمية — imports معقدة تحتاج تدخلاً يدوياً
    if issue.file_path in PROTECTED_FILES:
        return None
    for pattern, fix_func in FIX_REGISTRY.items():
        if pattern in issue.title:
            return fix_func
    return None


# ═══ دوال مساعدة ═══

def _resolve_path(file_path: str, project_root: Path) -> Optional[Path]:
    """تحويل مسار نسبي من التقرير إلى مسار مطلق"""
    full = project_root / file_path
    if full.exists():
        return full
    # جرب المسار مع ../ للخلف
    alt = Path("/home/ngm") / file_path
    if alt.exists():
        return alt
    return None


# ═══ إصلاحات Python ═══

@register_fix("استيراد غير مستخدم: '")
def fix_unused_python_import(issue: Issue, project_root: Path = None) -> bool:
    """إزالة سطر استيراد غير مستخدم من ملف Python"""
    root = project_root or PROJECT_ROOT
    file_path = _resolve_path(issue.file_path, root)
    if not file_path or not issue.line_number:
        return False

    try:
        lines = file_path.read_text(encoding="utf-8").split("\n")
        line_idx = issue.line_number - 1

        if line_idx < 0 or line_idx >= len(lines):
            return False

        # استخراج اسم المتغير من العنوان
        match = re.search(r"استيراد غير مستخدم: '(\w+)'", issue.title)
        if not match:
            return False
        unused_name = match.group(1)

        target_line = lines[line_idx]

        # تجاهل imports متعددة الأسطر (معقدة للإصلاح الآمن — تحتاج تدخلاً يدوياً)
        if "(" in target_line and ")" not in target_line:
            return False
        # تجاهل الأسطر المنزاحة (جزء من import متعدد الأسطر)
        if target_line and target_line[0] in (" ", "\t") and not target_line.strip().startswith(("from ", "import ")):
            return False

        # الحالة 1: import module — احذف السطر كاملاً
        if re.match(rf"^import\s+{unused_name}\b", target_line):
            lines[line_idx] = ""
        # الحالة 2: from module import name — احذف الاسم فقط
        elif "import" in target_line and unused_name in target_line:
            # from X import a, b, c
            new_line = _remove_from_import_line(target_line, unused_name)
            if new_line is None:
                lines[line_idx] = ""  # آخر اسم في السطر — احذف الكل
            else:
                lines[line_idx] = new_line
        else:
            return False

        # كتابة الملف بدون أسطر فارغة زائدة
        clean_lines = _clean_empty_lines(lines)
        file_path.write_text("\n".join(clean_lines) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def _remove_from_import_line(line: str, name: str) -> Optional[str]:
    """إزالة اسم من سطر import - ترجع None إذا كان الاسم الوحيد"""
    # from X import a, b, c
    match = re.match(r"(from\s+\S+\s+import\s+)(.+)$", line)
    if not match:
        return None
    prefix = match.group(1)
    items = match.group(2)
    # تقسيم الأسماء مع مراعاة as
    parts = [p.strip() for p in items.split(",")]
    new_parts = []
    for p in parts:
        # تحقق من name أو name as alias
        if p == name or p.startswith(f"{name} "):
            continue
        new_parts.append(p)

    if not new_parts:
        return None  # احذف السطر بأكمله
    return prefix + ", ".join(new_parts)


def _clean_empty_lines(lines: list[str]) -> list[str]:
    """إزالة الأسطر الفارغة المتتالية (لا تزيد عن 2)"""
    result = []
    empty_count = 0
    for line in lines:
        if line.strip() == "":
            empty_count += 1
            if empty_count <= 2:
                result.append(line)
        else:
            empty_count = 0
            result.append(line)
    # إزالة الفراغ في البداية
    while result and result[0].strip() == "":
        result.pop(0)
    return result


# ═══ إصلاحات JSX ═══

@register_fix("استيراد غير مستخدم: '")
def fix_unused_jsx_import(issue: Issue, project_root: Path = None) -> bool:
    """إزالة استيراد غير مستخدم من كتلة import في JSX (خاص بـ lucide-react)"""
    root = project_root or PROJECT_ROOT
    file_path = _resolve_path(issue.file_path, root)
    if not file_path or not issue.line_number:
        return False

    try:
        lines = file_path.read_text(encoding="utf-8").split("\n")
        line_idx = issue.line_number - 1

        if line_idx < 0 or line_idx >= len(lines):
            return False

        # استخراج اسم الأيقونة
        match = re.search(r"استيراد غير مستخدم: '(\w+(?:\s+as\s+\w+)?)'", issue.title)
        if not match:
            return False
        icon_name = match.group(1)

        target_line = lines[line_idx]

        # إزالة الاسم من import { X, Y, Z } from 'lucide-react'
        new_line = _remove_from_jsx_import(target_line, icon_name)
        if new_line is None:
            lines[line_idx] = ""
        else:
            lines[line_idx] = new_line

        clean_lines = _clean_empty_lines(lines)
        file_path.write_text("\n".join(clean_lines) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def _remove_from_jsx_import(line: str, name: str) -> Optional[str]:
    """إزالة اسم من import { a, b, c } from 'module'"""
    # التعامل مع as alias: 'Clock as ClockIcon'
    base_name = name.split(" as ")[0].strip()

    match = re.match(r"(import\s*\{)([^}]+)(\}\s*from\s*.+)$", line)
    if not match:
        return None

    prefix = match.group(1)
    items_str = match.group(2)
    suffix = match.group(3)

    parts = [p.strip() for p in items_str.split(",") if p.strip()]
    new_parts = []
    for p in parts:
        p_base = p.split(" as ")[0].strip()
        if p_base == base_name:
            continue
        new_parts.append(p)

    if not new_parts:
        return None  # آخر اسم — احذف السطر

    new_items = ", ".join(new_parts)
    return f"{prefix} {new_items} {suffix}"


# ═══ إصلاحات useState غير المستخدمة ═══

@register_fix("حالة useState غير مستخدمة: '")
def fix_unused_use_state(issue: Issue, project_root: Path = None) -> bool:
    """إزالة سطر const [var, setVar] = useState(...) غير المستخدم"""
    root = project_root or PROJECT_ROOT
    file_path = _resolve_path(issue.file_path, root)
    if not file_path or not issue.line_number:
        return False

    try:
        lines = file_path.read_text(encoding="utf-8").split("\n")
        line_idx = issue.line_number - 1

        if line_idx < 0 or line_idx >= len(lines):
            return False

        target = lines[line_idx]
        # التحقق من أنه سطر useState
        if "useState" not in target:
            return False

        lines[line_idx] = ""
        clean_lines = _clean_empty_lines(lines)
        file_path.write_text("\n".join(clean_lines) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


# ═══ إصلاحات الأمان ═══

@register_fix("توكن مكشوف في shell script")
def fix_hardcoded_token_in_shell(issue: Issue, project_root: Path = None) -> bool:
    """استبدال التوكن المكشوف بـ source .env"""
    root = project_root or PROJECT_ROOT
    file_path = _resolve_path(issue.file_path, root)
    if not file_path:
        return False

    try:
        lines = file_path.read_text(encoding="utf-8").split("\n")
        line_idx = (issue.line_number or 1) - 1

        if 0 <= line_idx < len(lines):
            line = lines[line_idx]
            if "export" in line and "=" in line and not "your_" in line.lower():
                # تعليق السطر القديم
                lines[line_idx] = f"# تم النقل لـ .env: {line.strip()}"

        # إضافة source .env إذا لم يكن موجوداً
        has_source = any("source" in l and ".env" in l for l in lines)
        if not has_source:
            # إدراج بعد #!/bin/bash
            insert_at = 1 if lines[0].startswith("#!") else 0
            env_rel_path = os.path.relpath(
                str(root / "istxbot" / ".env"),
                str(file_path.parent)
            )
            lines.insert(insert_at, f'set -a && source "{env_rel_path}" 2>/dev/null && set +a')

        file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


# ═══ إصلاحات الهيكلة ═══

@register_fix("مجلد فارغ: ")
def fix_empty_directory(issue: Issue, project_root: Path = None) -> bool:
    """حذف مجلد فارغ"""
    root = project_root or PROJECT_ROOT
    dir_path = root / issue.file_path.rstrip("/")
    if not dir_path.exists() or not dir_path.is_dir():
        return False
    try:
        if not list(dir_path.iterdir()):
            dir_path.rmdir()
            return True
        return False
    except Exception:
        return False


# ═══ إصلاحات API ═══

def fix_missing_route_decorator(issue: Issue, project_root: Path = None) -> bool:
    """إضافة @app.route لدالة تفتقده — يحتاج تأكيد يدوي للمسار الصحيح"""
    # هذا الإصلاح نصف تلقائي — يضيف تعليق توجيهي بدل المسار الفعلي
    root = project_root or PROJECT_ROOT
    file_path = _resolve_path(issue.file_path, root)
    if not file_path or not issue.line_number:
        return False

    try:
        lines = file_path.read_text(encoding="utf-8").split("\n")
        line_idx = issue.line_number - 1

        if line_idx < 0 or line_idx >= len(lines):
            return False

        # استخراج اسم الدالة
        match = re.search(r"دالة (\w+)\(\)", issue.title)
        if not match:
            return False
        func_name = match.group(1)

        # البحث عن الدالة في الملف
        for i, line in enumerate(lines):
            if f"def {func_name}(" in line:
                # إدراج route decorator قبلها
                lines.insert(i, "TODO_ADD_ROUTE = '/api/admin/...'  # حدد المسار الصحيح ثم احذف هذا السطر")
                lines.insert(i, "# @app.route(TODO_ADD_ROUTE, methods=['GET', 'POST'])  # فك التعليق بعد تحديد المسار")
                break

        file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False

# تسجيل fix_missing_route_decorator بنمطين (الدالة تظهر بعنوانين مختلفين)
FIX_REGISTRY["دالة"] = fix_missing_route_decorator
FIX_REGISTRY["تفتقد @app.route"] = fix_missing_route_decorator


