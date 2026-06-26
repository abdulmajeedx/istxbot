#!/bin/bash
# ═══════════════════════════════════════════════════════
# سكربت نشر istxbot عبر Docker
# ═══════════════════════════════════════════════════════
set -e

RED='\033[91m'
GREEN='\033[92m'
CYAN='\033[96m'
YELLOW='\033[93m'
RESET='\033[0m'

echo -e "${CYAN}╔══════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║   🐳  نشر istxbot على Docker                ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${RESET}"
echo ""

# ── التحقق من Docker ──
if ! docker --version &>/dev/null; then
    echo -e "${RED}❌ Docker غير مثبت. ثبتّه أولاً:${RESET}"
    echo "   curl -fsSL https://get.docker.com | bash"
    exit 1
fi
echo -e "${GREEN}✅ Docker $(docker --version | cut -d' ' -f3)${RESET}"

# ── نسخ .env إن لم يكن موجوداً ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOCKER_DIR="$(dirname "$SCRIPT_DIR")/docker"
cd "$DOCKER_DIR"

if [ ! -f .env ]; then
    if [ -f ../istxbot/.env ]; then
        echo -e "${YELLOW}📋 نسخ .env من المشروع...${RESET}"
        cp ../istxbot/.env .env
        echo -e "${GREEN}✅ تم النسخ${RESET}"
    elif [ -f .env.example ]; then
        echo -e "${YELLOW}⚠️  .env غير موجود. انسخ .env.example واملأ القيم:${RESET}"
        echo "   cp docker/.env.example docker/.env"
        echo "   nano docker/.env"
        exit 1
    fi
fi

# ── إيقاف خدمات systemd القديمة (اختياري) ──
echo ""
echo -e "${YELLOW}⏸️  إيقاف خدمات systemd القديمة...${RESET}"
for svc in telegram-bot bot-web-control dev-bot monitor; do
    if systemctl is-active --quiet $svc 2>/dev/null; then
        sudo systemctl stop $svc 2>/dev/null && echo -e "  ✅ أوقفت $svc" || echo -e "  ⚠️  تعذر إيقاف $svc"
        sudo systemctl disable $svc 2>/dev/null || true
    else
        echo -e "  ⏭️  $svc غير نشطة"
    fi
done

# ── بناء الصور ──
echo ""
echo -e "${CYAN}🔨 بناء صور Docker...${RESET}"
docker compose build --pull

# ── تشغيل الخدمات ──
echo ""
echo -e "${CYAN}🚀 تشغيل الخدمات...${RESET}"
docker compose up -d

# ── انتظار وتحقق ──
echo ""
echo -e "${YELLOW}⏳ انتظار اكتمال التشغيل...${RESET}"
sleep 5
docker compose ps

# ── فحص الصحة ──
echo ""
echo -e "${CYAN}🩺 فحص صحة الخدمات...${RESET}"
if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ الويب: http://localhost:8080/health${RESET}"
else
    echo -e "${YELLOW}⚠️  الويب لم يستجب بعد (قد يحتاج وقتاً)${RESET}"
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}║   ✅  تم النشر بنجاح!                       ║${RESET}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "📋 ${CYAN}أوامر مفيدة:${RESET}"
echo -e "   السجلات:    ${YELLOW}docker compose logs -f [اسم_الخدمة]${RESET}"
echo -e "   الحالة:     ${YELLOW}docker compose ps${RESET}"
echo -e "   إعادة تشغيل: ${YELLOW}docker compose restart [اسم_الخدمة]${RESET}"
echo -e "   إيقاف:      ${YELLOW}docker compose down${RESET}"
echo -e "   تحديث:      ${YELLOW}git pull && docker compose up -d --build${RESET}"
echo ""
echo -e "🔗 ${CYAN}الروابط:${RESET}"
echo -e "   الموقع:     http://localhost:8080"
echo -e "   المشرف:     http://localhost:8082"
echo -e "   المراقبة:   http://localhost:8090"
