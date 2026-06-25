# ساحِب — لوحة تحكم React

لوحة تحكم احترافية لبوت @istxbot مبنية بـ React + Vite + Tailwind + Recharts.

## التشغيل

```bash
npm install
npm run dev       # تطوير على http://localhost:5173
npm run build     # بناء للإنتاج → dist/
```

## الهيكل

```
src/
├── api/client.js          # 55+ API endpoint
├── contexts/AuthContext.jsx  # مصادقة + 2FA
├── layouts/DashboardLayout.jsx  # شريط جانبي + تنقل
├── pages/
│   ├── LoginPage.jsx      # تسجيل دخول + 2FA
│   ├── DashboardPage.jsx  # لوحة تحكم رئيسية
│   ├── UsersPage.jsx      # إدارة المستخدمين
│   ├── SettingsPage.jsx   # إعدادات + منصات + مستويات
│   ├── LogsPage.jsx       # سجلات مع فلترة
│   └── AnalyticsPage.jsx  # تحليلات ورسوم بيانية
└── index.css              # Tailwind + تأثيرات
```

## النشر

```bash
npm run build
# انسخ dist/ إلى السيرفر
cp -r dist/* /var/www/admin/
```

أو شغّل عبر nginx proxy:
```
location /admin/ {
    proxy_pass http://127.0.0.1:5173/;
}
```

## المميزات

- 🌙 تصميم داكن كامل
- 📱 متجاوب مع الجوال
- 🔒 مصادقة بخطوتين (2FA)
- 📊 رسوم بيانية تفاعلية
- 🔍 بحث وتصفية متقدمة
- 🌐 RTL كامل بالعربية
- ⚡ تحديث لحظي كل 30 ثانية
