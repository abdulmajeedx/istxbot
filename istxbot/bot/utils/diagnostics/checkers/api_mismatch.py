"""
فاحص تطابق API — يقارن مسارات Frontend (React) مع Backend (Flask)
يدعم وجود Backend منفصلين: web_control.py (port 8082) و istxbot (port 8080)
"""

import re
import ast
from pathlib import Path
from typing import Optional

from ..models import Issue, Severity

# ═══ ثوابت ═══

# أنماط استخراج المسارات من client.js
ROUTE_PATTERNS = [
    # نمط: client.get('/path'), client.post('/path', data), إلخ
    re.compile(r"""(?:client\.)?(get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]"""),
    # نمط: api.get('/path', ...)
    re.compile(r"""(\w+)\.(get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]"""),
]

# مسارات لتجاهلها (ليست API حقيقية)
IGNORED_PATHS = {
    "/", "/health", "/help", "/contact", "/account", "/sw.js",
    "/login", "/login-2fa", "/dashboard",
}

# الملفات للفحص
PROJECT_ROOT = Path("/home/ngm/istxbot")
ADMIN_PANEL_CLIENT = PROJECT_ROOT / "admin-panel/src/api/client.js"
WEB_CONTROL_PY = Path("/home/ngm/bot_download_telegram/web/web_control.py")
ISTXBOT_ROUTES_DIR = PROJECT_ROOT / "istxbot/web/routes"


def _extract_frontend_routes(client_js_path: Path) -> list[dict]:
    """استخراج جميع مسارات API من ملف client.js"""
    routes = []
    if not client_js_path.exists():
        return routes

    content = client_js_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # البحث عن تعريفات دوال API
    # نمط: functionName(params) { return this.get('/path', ...) }
    func_pattern = re.compile(r"""(\w+)\s*\([^)]*\)\s*\{[^}]*?(?:get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]""")

    for i, line in enumerate(lines, 1):
        # تجاهل التعليقات
        if line.strip().startswith("//"):
            continue

        for pattern in ROUTE_PATTERNS:
            for match in pattern.finditer(line):
                method = match.group(1).upper()
                # إذا كان النمط الثاني (module.method)، فالطريقة هي group(2)
                if pattern == ROUTE_PATTERNS[1]:
                    method = match.group(2).upper()
                    path = match.group(3)
                else:
                    method = match.group(1).upper()
                    path = match.group(2)

                if path in IGNORED_PATHS:
                    continue
                if path.startswith("/"):
                    routes.append({
                        "method": method,
                        "path": path,
                        "source_file": str(client_js_path.relative_to(PROJECT_ROOT)),
                        "source_line": i,
                    })
    return routes


def _extract_backend_routes(py_file_path: Path) -> list[dict]:
    """استخراج جميع المسارات المسجلة في ملف Flask (باستخدام AST)"""
    routes = []
    if not py_file_path.exists():
        return routes

    try:
        tree = ast.parse(py_file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return routes

    for node in ast.walk(tree):
        # البحث عن @bp.route('/path', methods=[...]) أو @app.route('/path', methods=[...])
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    # decorator.func قد يكون app.route أو bp.route أو admin_bp.route
                    func = decorator.func
                    decorator_name = ""
                    if isinstance(func, ast.Attribute):
                        decorator_name = func.attr  # 'route'
                    elif isinstance(func, ast.Name):
                        decorator_name = func.id

                    if decorator_name == "route" and decorator.args:
                        path = None
                        methods = ["GET"]

                        # استخراج path
                        if isinstance(decorator.args[0], ast.Constant):
                            path = decorator.args[0].value
                        elif isinstance(decorator.args[0], ast.BinOp):
                            # للتعامل مع '/api/admin/' + ADMIN_PATH
                            try:
                                path = ast.literal_eval(decorator.args[0])
                            except Exception:
                                path = "[DYNAMIC_PATH]"

                        # استخراج methods من keywords
                        for kw in decorator.keywords:
                            if kw.arg == "methods":
                                try:
                                    methods = [elt.value.upper() for elt in kw.value.elts]
                                except Exception:
                                    pass

                        if path and path not in IGNORED_PATHS:
                            routes.append({
                                "method": ", ".join(sorted(methods)),
                                "path": str(path),
                                "source_file": str(py_file_path.relative_to(PROJECT_ROOT.parent))
                                    if py_file_path.is_relative_to(PROJECT_ROOT.parent)
                                    else str(py_file_path),
                                "source_line": node.lineno,
                                "function": node.name,
                            })

    return routes


def _normalize_path(path: str) -> str:
    """توحيد شكل المسار للمقارنة (إزالة /api/ prefix، إزالة <int:...>  إلخ)"""
    p = path.rstrip("/")
    # تحويل معاملات Flask إلى شكل موحد
    p = re.sub(r"<int:(\w+)>", r"{\1}", p)
    p = re.sub(r"<(\w+)>", r"{\1}", p)
    return p


def check_api_mismatch(project_root: Optional[Path] = None) -> list[Issue]:
    """
    الفاحص الرئيسي: مقارنة مسارات Frontend مع Backend
    يفحص كلاً من web_control.py (port 8082 - لوحة الإدارة) و istxbot (port 8080 - الموقع العام)
    """
    issues: list[Issue] = []
    root = project_root or PROJECT_ROOT

    # 1. استخراج مسارات Frontend
    frontend_routes = _extract_frontend_routes(ADMIN_PANEL_CLIENT)

    # 2. استخراج مسارات Backend من web_control.py (port 8082 - الخادم الفعلي للوحة الإدارة)
    web_control_routes = _extract_backend_routes(WEB_CONTROL_PY)

    # 3. استخراج مسارات Backend من istxbot (port 8080)
    istxbot_routes = []
    if ISTXBOT_ROUTES_DIR.exists():
        for py_file in sorted(ISTXBOT_ROUTES_DIR.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            istxbot_routes.extend(_extract_backend_routes(py_file))

    # دمج جميع مسارات الـ backend
    all_backend_routes = web_control_routes + istxbot_routes

    # ═══ المقارنة: Frontend vs Backend ═══

    # بناء فهرس سريع للمسارات الخلفية
    backend_index: dict[str, set[str]] = {}  # path -> {methods}
    for br in all_backend_routes:
        norm_path = _normalize_path(br["path"])
        if norm_path not in backend_index:
            backend_index[norm_path] = set()
        for m in br["method"].split(", "):
            backend_index[norm_path].add(m)

    for fr in frontend_routes:
        norm_fr_path = _normalize_path(fr["path"])
        # البحث عن تطابق مباشر
        if norm_fr_path in backend_index:
            if fr["method"] not in backend_index[norm_fr_path]:
                issues.append(Issue(
                    severity=Severity.HIGH,
                    category="api",
                    title=f"عدم تطابق HTTP method: {fr['method']} {fr['path']}",
                    solution=f"الـ Frontend يستخدم {fr['method']} لكن الـ Backend يدعم فقط: {', '.join(sorted(backend_index[norm_fr_path]))}. "
                             f"عدل client.js لتستخدم الطريقة الصحيحة أو أضف الدعم في الـ Backend.",
                    file_path=fr["source_file"],
                    line_number=fr["source_line"],
                ))
            # تطابق تام - لا مشكلة
            continue

        # البحث عن مسار مشابه (مع اختلاف prefix)
        found = False
        for be_path, be_methods in backend_index.items():
            # هل مسار الـ frontend موجود كجزء من مسار backend أطول؟
            if norm_fr_path == be_path:
                found = True
                break
            # هل مسار الـ backend ينتهي بمسار الـ frontend؟
            if be_path.endswith(norm_fr_path):
                found = True
                if fr["method"] not in be_methods:
                    issues.append(Issue(
                        severity=Severity.HIGH,
                        category="api",
                        title=f"عدم تطابق HTTP method لـ {fr['method']} {fr['path']}",
                        solution=f"المسار موجود في الـ Backend كـ {be_path} لكن بـ {', '.join(sorted(be_methods))}. "
                                 f"الـ Frontend يستخدم {fr['method']}.",
                        file_path=fr["source_file"],
                        line_number=fr["source_line"],
                    ))
                break

        if not found:
            # هذا المسار غير موجود إطلاقاً
            issues.append(Issue(
                severity=Severity.CRITICAL,
                category="api",
                title=f"مسار API غير موجود في الـ Backend: {fr['method']} {fr['path']}",
                solution=f"هذا المسار يستدعى من الـ Frontend لكن لا يوجد له مقابل في أي Backend. "
                         f"إما أضف المسار في web_control.py أو istxbot، أو صحح client.js لاستخدام المسار الصحيح.",
                file_path=fr["source_file"],
                line_number=fr["source_line"],
                code_snippet=f"{fr['method']} {fr['path']}",
            ))

    # ═══ فحص decorators مفقودة ═══

    if WEB_CONTROL_PY.exists():
        try:
            content = WEB_CONTROL_PY.read_text(encoding="utf-8")
            # البحث عن دوال بدون @app.route (مثل admin_tier_config المعروفة)
            func_defs = re.findall(r"^def (\w+)\(", content, re.MULTILINE)
            for func_name in func_defs:
                # تجاهل الدوال المساعدة
                if func_name.startswith("_") or func_name in ("index", "main"):
                    continue
                # ابحث عن @app.route قبل هذه الدالة
                func_pos = content.find(f"def {func_name}(")
                before_func = content[:func_pos]
                # ابحث للخلف عن أقرب @app.route
                last_route = before_func.rfind("@app.route")
                last_def = before_func.rfind("def ")
                # إذا كان آخر def أقرب من آخر route، فالدالة بدون route
                if last_route == -1 or (last_def > last_route and last_def != -1):
                    # قد تكون دالة عادية — تجاهل إن كانت تحوي كلمات مساعدة
                    helper_keywords = (
                        "send_", "format_", "get_", "load_", "save_", "check_",
                        "add_", "record_", "generate_", "run_", "require_",
                        "is_", "has_", "validate_", "verify_", "build_",
                        "create_", "update_", "delete_", "parse_", "process_",
                        "log_", "track_", "cors", "locked", "failed", "successful",
                        "admin_check", "login_", "auth_", "ensure_", "init_",
                    )
                    if any(func_name.startswith(kw) for kw in helper_keywords):
                        continue
                    # دالة تبدو كـ handler بدون route
                    issues.append(Issue(
                        severity=Severity.HIGH,
                        category="api",
                        title=f"دالة {func_name}() قد تفتقد @app.route",
                        solution=f"الدالة {func_name} في web_control.py تبدو كمعالج API لكن بدون مسجل route. "
                                 f"أضف @app.route('/api/...') قبل تعريف الدالة.",
                        file_path=str(WEB_CONTROL_PY.relative_to(PROJECT_ROOT.parent))
                            if WEB_CONTROL_PY.is_relative_to(PROJECT_ROOT.parent)
                            else str(WEB_CONTROL_PY),
                        line_number=content[:func_pos].count("\n") + 1,
                    ))
        except Exception:
            pass

    # ═══ فحص تكرار تعريف المسارات بين الـ Backendين ═══

    web_control_paths = {_normalize_path(r["path"]) for r in web_control_routes}
    istxbot_paths = {_normalize_path(r["path"]) for r in istxbot_routes}
    duplicates = web_control_paths & istxbot_paths
    admin_duplicates = {p for p in duplicates if "/admin/" in p}
    if len(admin_duplicates) > 3:  # أكثر من 3 تداخلات تستحق التنبيه
        issues.append(Issue(
            severity=Severity.MEDIUM,
            category="api",
            title=f"تكرار {len(admin_duplicates)} مسار مشرف بين web_control.py و istxbot",
            solution="كلا الخادمين يعرفان نفس مسارات المشرف. هذا قد يسبب ارتباكاً. "
                     "حدد أياً منهما المسؤول عن لوحة الإدارة وركز مسارات المشرف فيه.",
            file_path="istxbot/web/routes/",
        ))

    return issues

