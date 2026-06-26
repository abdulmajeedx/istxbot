"""
نماذج البيانات لنظام فحص صحة المشروع
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from html import escape as html_escape
from typing import Optional


class Severity(Enum):
    CRITICAL = "🔴"
    HIGH = "🟠"
    MEDIUM = "🟡"
    LOW = "🔵"
    INFO = "⚪"

    @property
    def label_ar(self) -> str:
        """تسمية عربية لمستوى الخطورة"""
        return {
            Severity.CRITICAL: "حرج",
            Severity.HIGH: "عالي",
            Severity.MEDIUM: "متوسط",
            Severity.LOW: "منخفض",
            Severity.INFO: "معلومة",
        }[self]


@dataclass
class Issue:
    """يمثل مشكلة واحدة مكتشفة في المشروع"""
    severity: Severity
    category: str               # api, code_quality, structure, security, git, config
    title: str                  # وصف عربي مختصر (سطر واحد)
    solution: str               # الحل المقترح بالعربية
    file_path: str              # المسار النسبي للملف (من جذر المشروع)
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None   # مقتطف من الكود للسياق

    def __str__(self) -> str:
        line_info = f":{self.line_number}" if self.line_number else ""
        return (
            f"{self.severity.value} [{self.severity.label_ar}] {self.title}\n"
            f"   📁 {self.file_path}{line_info}\n"
            f"   💡 {self.solution}"
        )

    def telegram_line(self) -> str:
        """تنسيق مختصر للإرسال عبر تيليجرام - مع تعقيم HTML"""
        line_info = f" (سطر {self.line_number})" if self.line_number else ""
        return (
            f"{self.severity.value} <b>{html_escape(self.title)}</b>\n"
            f"   📁 <code>{html_escape(self.file_path)}</code>{line_info}\n"
            f"   💡 {html_escape(self.solution)}\n"
        )


@dataclass
class Report:
    """تقرير مجمع لنتائج الفحص"""
    timestamp: datetime = field(default_factory=datetime.now)
    issues: list[Issue] = field(default_factory=list)

    @property
    def total_issues(self) -> int:
        return len(self.issues)

    @property
    def by_severity(self) -> dict[Severity, int]:
        counts = {s: 0 for s in Severity}
        for issue in self.issues:
            counts[issue.severity] += 1
        return counts

    @property
    def by_category(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.category] = counts.get(issue.category, 0) + 1
        return counts

    @property
    def summary(self) -> str:
        """ملخص عربي قصير"""
        sev = self.by_severity
        parts = []
        if sev[Severity.CRITICAL]:
            parts.append(f"{sev[Severity.CRITICAL]} حرجة")
        if sev[Severity.HIGH]:
            parts.append(f"{sev[Severity.HIGH]} عالية")
        if sev[Severity.MEDIUM]:
            parts.append(f"{sev[Severity.MEDIUM]} متوسطة")
        if sev[Severity.LOW]:
            parts.append(f"{sev[Severity.LOW]} منخفضة")
        if not parts:
            return "✅ لا توجد مشاكل"
        return f"تم العثور على {self.total_issues} مشكلة ({', '.join(parts)})"
