"""
فاحص جودة الكود — استيرادات غير مستخدمة، كود ميت، قيم صلبة، أنماط خطيرة
"""

import re
import ast
from pathlib import Path
from typing import Optional

from ..models import Issue, Severity

PROJECT_ROOT = Path("/home/ngm/istxbot")

# ═══ فحص Python ═══

def _check_python_file(file_path: Path) -> list[Issue]:
    """فحص ملف Python واحد"""
    issues = []
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError):
        return issues

    lines = content.split("\n")
    rel_path = str(file_path.relative_to(PROJECT_ROOT))

    # ── استيرادات غير مستخدمة ──
    imported_names: dict[str, int] = {}  # name -> line
    used_names: set[str] = set()

    for node in ast.walk(tree):
        # جمع المستوردات
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                imported_names[name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                if name != "*":  # تجاهل wildcard imports
                    imported_names[name] = node.lineno
        # جمع المستخدمات
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)

    for name, lineno in imported_names.items():
        if name not in used_names and not name.startswith("_"):
            # تجاهل imports الشائعة في __init__.py
            if file_path.name == "__init__.py":
                continue
            issues.append(Issue(
                severity=Severity.LOW,
                category="code_quality",
                title=f"استيراد غير مستخدم: '{name}'",
                solution=f"احذف '{name}' من قائمة imports في السطر {lineno}.",
                file_path=rel_path,
                line_number=lineno,
            ))

    # ── كود ميت (دوال داخل دوال بعد return) ──
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for i, stmt in enumerate(node.body):
                if isinstance(stmt, ast.Return) and i < len(node.body) - 1:
                    # يوجد كود بعد return - قد يكون كود ميت
                    next_stmt = node.body[i + 1]
                    if not isinstance(next_stmt, (ast.Return, ast.Expr)) or (
                        isinstance(next_stmt, ast.Expr) and
                        isinstance(next_stmt.value, ast.Constant) and
                        isinstance(next_stmt.value.value, str) and
                        (next_stmt.value.value.startswith('"""') or next_stmt.value.value.startswith("'''"))
                    ):
                        # ليس docstring — قد يكون كود ميت
                        pass  # نتجاهل لتجنب false positives
                    break

    # ── استخدام asyncio.run في دوال غير async (نمط شائع خاطئ) ──
    # هذا الفحص معطل لأنه نمط شائع ومقبول في هذا المشروع

    # ── طباعة توكنات/أسرار ──
    secret_patterns = [
        (r"(?:TOKEN|SECRET|PASSWORD|API_KEY)\s*=\s*['\"]([^'\"]{8,})['\"]", Severity.CRITICAL),
        (r"(?:token|secret|password)\s*=\s*['\"]([^'\"]{8,})['\"]", Severity.HIGH),
    ]
    for pattern, sev in secret_patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            value = match.group(1)
            # تجاهل المتغيرات البيئية
            if "os.getenv" in content[max(0, match.start()-100):match.start()]:
                continue
            if value in ("", "changeme", "your-token-here", "xxx"):
                continue
            line_no = content[:match.start()].count("\n") + 1
            issues.append(Issue(
                severity=sev,
                category="security",
                title=f"سر مكشوف في الكود: {match.group(0)[:50]}...",
                solution="استخدم متغير بيئة (os.getenv) بدلاً من تضمين الأسرار مباشرة في الكود.",
                file_path=rel_path,
                line_number=line_no,
            ))

    return issues


# ═══ فحص JavaScript/JSX ═══

def _check_jsx_file(file_path: Path) -> list[Issue]:
    """فحص ملف JSX/JS واحد"""
    issues = []
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")
    except UnicodeDecodeError:
        return issues

    rel_path = str(file_path.relative_to(PROJECT_ROOT))

    # ── استيرادات غير مستخدمة من lucide-react ──
    # نمط: import { X, Y, Z } from 'lucide-react'
    lucide_imports = re.findall(
        r"""import\s*\{([^}]+)\}\s*from\s*['"]lucide-react['"]""",
        content
    )
    for import_block in lucide_imports:
        icons = [name.strip() for name in import_block.split(",")]
        for icon in icons:
            if not icon:
                continue
            # هل الأيقونة مستخدمة كـ <IconName /> أو IconName في JSX؟
            if not re.search(rf"\b{icon}\b", content[content.find(import_block) + len(import_block):]):
                line_no = content[:content.find(icon)].count("\n") + 1
                issues.append(Issue(
                    severity=Severity.LOW,
                    category="code_quality",
                    title=f"استيراد غير مستخدم: '{icon}' من lucide-react",
                    solution=f"احذف '{icon}' من قائمة الاستيراد في السطر {line_no}.",
                    file_path=rel_path,
                    line_number=line_no,
                ))

    # ── مفاتيح JSX صلبة الترميز (hardcoded labels) ──
    # ابحث عن defaultChecked={true} أو checked={true} بدون متغير
    hardcoded_checks = re.finditer(
        r"""(defaultChecked|checked)\s*=\s*\{(true|false)\}""",
        content
    )
    for match in hardcoded_checks:
        line_no = content[:match.start()].count("\n") + 1
        # تحقق من السياق — هل هو داخل مكون Security/Settings toggle؟
        context_start = max(0, match.start() - 300)
        context = content[context_start:match.start()]
        if "onChange" not in context and "handle" not in context.lower():
            issues.append(Issue(
                severity=Severity.MEDIUM,
                category="code_quality",
                title="قيمة صلبة الترميز في toggle/checkbox بدون onChange",
                solution="اربط هذه القيمة بمتغير حالة (useState) وأضف معالج onChange لحفظ التغيير.",
                file_path=rel_path,
                line_number=line_no,
                code_snippet=match.group(0),
            ))

    # ── كود ميت: متغيرات/حالات غير مستخدمة ──
    # useState بدون استخدام
    state_pattern = re.finditer(
        r"""const\s*\[(\w+),\s*set\w+\]\s*=\s*useState\(""",
        content
    )
    for match in state_pattern:
        var_name = match.group(1)
        after_decl = content[match.end():]
        # هل المتغير مستخدم بعد تعريفه؟
        var_uses = len(re.findall(rf"\b{var_name}\b", after_decl))
        if var_uses <= 1:  # مرة واحدة فقط (ربما في JSX واحدة أو لا شيء)
            line_no = content[:match.start()].count("\n") + 1
            issues.append(Issue(
                severity=Severity.MEDIUM,
                category="code_quality",
                title=f"حالة useState غير مستخدمة: '{var_name}'",
                solution=f"المتغير '{var_name}' معرف بـ useState لكنه لا يستخدم. احذفه أو استخدمه.",
                file_path=rel_path,
                line_number=line_no,
            ))

    # ═══ فحص أنماط محددة معروفة في admin-panel ═══

    # TODO في الكود
    for match in re.finditer(r"//\s*TODO|//\s*FIXME|//\s*HACK", content):
        line_no = content[:match.start()].count("\n") + 1
        issues.append(Issue(
            severity=Severity.INFO,
            category="code_quality",
            title=f"علامة TODO/FIXME: {lines[line_no-1].strip()[:80]}",
            solution="أكمل تنفيذ هذه الميزة أو احذف العلامة إن لم تعد مطلوبة.",
            file_path=rel_path,
            line_number=line_no,
        ))

    # استيراد ديناميكي مكرر (import() لنفس module محمل statically)
    static_imports = set()
    for m in re.finditer(r"""import\s+\{([^}]+)\}\s+from\s+['"]([^'"]+)['"]""", content):
        static_imports.add(m.group(2))
    for m in re.finditer(r"""await\s+import\s*\(\s*['"]([^'"]+)['"]""", content):
        dynamic_module = m.group(1)
        if dynamic_module in static_imports:
            line_no = content[:m.start()].count("\n") + 1
            issues.append(Issue(
                severity=Severity.LOW,
                category="code_quality",
                title=f"استيراد ديناميكي مكرر: import('{dynamic_module}')",
                solution=f"'{dynamic_module}' مستورد مسبقاً بشكل static. استخدم المرجع الموجود بدل import().",
                file_path=rel_path,
                line_number=line_no,
            ))

    return issues


def check_code_quality(project_root: Optional[Path] = None) -> list[Issue]:
    """فاحص جودة الكود الرئيسي"""
    issues: list[Issue] = []
    root = project_root or PROJECT_ROOT

    # فحص ملفات Python
    python_dirs = [
        root / "istxbot",
        root / "dev-bot",
        root / "monitor",
    ]
    for py_dir in python_dirs:
        if not py_dir.exists():
            continue
        for py_file in py_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            if "diagnostics" in str(py_file):  # لا تفحص أداة التشخيص نفسها
                continue
            if py_file.stat().st_size > 100_000:  # تجاهل الملفات الكبيرة جداً
                continue
            issues.extend(_check_python_file(py_file))

    # فحص ملفات JSX/JS
    jsx_dir = root / "admin-panel/src"
    if jsx_dir.exists():
        for jsx_file in jsx_dir.rglob("*.jsx"):
            issues.extend(_check_jsx_file(jsx_file))
        for js_file in jsx_dir.rglob("*.js"):
            if "node_modules" in str(js_file):
                continue
            issues.extend(_check_jsx_file(js_file))

    return issues

