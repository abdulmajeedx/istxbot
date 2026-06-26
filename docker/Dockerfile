# ═══ صورة أساسية لجميع خدمات Python في مشروع istxbot ═══
FROM python:3.11-slim

# ── تبعيات النظام ──
# ffmpeg: مطلوب لـ yt-dlp لتحميل ومعالجة الفيديو
# supervisor: لإدارة العمليات داخل الحاوية إذا احتجنا
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── الاعتماديات الأساسية لجميع الخدمات ──
RUN pip install --no-cache-dir \
    aiogram>=3.0 \
    flask>=3.0 \
    waitress>=3.0 \
    yt-dlp>=2024.0 \
    requests>=2.31 \
    python-dotenv>=1.0 \
    aiosqlite>=0.20 \
    cryptography>=41.0 \
    psutil>=5.9 \
    gunicorn>=21.0 \
    python-telegram-bot>=20.0

# ── مجلد العمل ──
WORKDIR /app

# ── مجلدات البيانات ──
RUN mkdir -p /app/data /app/downloads /app/logs

# ── الصحة ──
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${WEB_PORT:-8080}/health || exit 1

CMD ["python3"]
