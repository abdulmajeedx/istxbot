#!/usr/bin/env python3
"""لوحة مراقبة السيرفر والبوتات — TikTokForBot Monitor"""

from datetime import datetime

from pathlib import Path

app = Flask(__name__)
BOT_DB = Path("/home/ngm/bot_download_telegram/bot_data.db")
DEV_DB = Path("/home/ngm/bot_dev/bot_data.db")

HTML = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TikTokForBot • مراقب</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui;background:#0d1117;color:#e6edf3;padding:16px}
h1{font-size:1.3em;margin-bottom:12px;color:#58a6ff}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px}
.card h2{font-size:0.9em;color:#8b949e;margin-bottom:8px;text-transform:uppercase}
.val{font-size:1.6em;font-weight:bold}
.green{color:#3fb950}.red{color:#f85149}.yellow{color:#d2991d}
.status{display:flex;align-items:center;gap:8px;margin:4px 0}
.dot{width:10px;height:10px;border-radius:50%}.dot-up{background:#3fb950}.dot-down{background:#f85149}
.bar{height:6px;background:#21262d;border-radius:3px;margin:6px 0;overflow:hidden}
.bar-fill{height:100%;border-radius:3px;transition:width 0.5s}
.mono{font-family:monospace;font-size:0.85em;color:#7ee787}
.logs{max-height:200px;overflow-y:auto;font-size:0.75em;background:#0d1117;padding:8px;border-radius:4px}
.logs div{border-bottom:1px solid #21262d;padding:2px 0}
.refresh{font-size:0.7em;color:#484f58;text-align:center;margin-top:12px}
.btn{display:inline-block;padding:4px 12px;border-radius:4px;border:1px solid #30363d;background:#21262d;color:#c9d1d9;cursor:pointer;text-decoration:none;font-size:0.8em;margin:2px}
.btn:hover{background:#30363d}
</style></head>
<body>
<h1>🤖 TikTokForBot • لوحة المراقبة</h1>
<div class="grid">
{% for card in cards %}
<div class="card">
<h2>{{ card.title }}</h2>
{% for item in card.rows %}
<div class="status"><div class="dot {{ 'dot-up' if item.ok else 'dot-down' }}"></div>
<span>{{ item.label }}: <strong class="{{ 'green' if item.ok else 'red' }}">{{ item.value }}</strong></span></div>
{% endfor %}
{% if card.bar %}<div class="bar"><div class="bar-fill" style="width:{{card.bar}}%;background:{%if card.bar>80%}#f85149{%elif card.bar>60%}#d2991d{%else%}#3fb950{%endif%}"></div></div><small>{{card.bar}}%</small>{% endif %}
</div>
{% endfor %}
</div>
<div class="card" style="margin-top:12px"><h2>📜 آخر السجلات</h2>
<div class="logs">{% for line in log_lines %}<div class="mono">{{ line }}</div>{% endfor %}</div></div>
<div class="refresh">⏱️ تحديث تلقائي كل 5 ثوانٍ | {{ now }}</div>
<meta http-equiv="refresh" content="5">
</body></html>"""

def get_service(name):
    try:
        r = subprocess.run(["systemctl","is-active",name],capture_output=True,text=True,timeout=5)
        return r.stdout.strip()
    except: return "unknown"

def get_db_counts(db_path):
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM visitors")
        users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM visitors WHERE last_visit > datetime('now','-1 day')")
        active = c.fetchone()[0]
        conn.close()
        return users, active
    except: return 0, 0

@app.route("/")
def dashboard():
    # حالة النظام
    cpu = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    boot = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M")

    # حالة الخدمات
    web_status = get_service("dev-bot")
    bot_status = get_service("telegram-bot")
    nginx_status = get_service("nginx")

    # إحصائيات البوتات
    bot_users, bot_active = get_db_counts(BOT_DB)
    dev_users, dev_active = get_db_counts(DEV_DB)

    # السجلات
    r = subprocess.run(["journalctl","-u","telegram-bot","--no-pager","-n","10"],capture_output=True,text=True,timeout=5)
    logs = [l.strip() for l in r.stdout.strip().split("\n")[-10:] if l.strip()]

    cards = [
        {"title":"🖥️ السيرفر", "rows":[
            {"label":"CPU","value":f"{cpu}%","ok":cpu<80},
            {"label":"RAM","value":f"{mem}%","ok":mem<85},
            {"label":"قرص","value":f"{disk}%","ok":disk<90},
            {"label":"التشغيل منذ","value":boot,"ok":True}
        ],"bar":max(cpu,mem,disk)},
        {"title":"🤖 @tiktokforbot", "rows":[
            {"label":"الحالة","value":bot_status,"ok":bot_status=="active"},
            {"label":"المستخدمين","value":str(bot_users),"ok":True},
            {"label":"نشط اليوم","value":str(bot_active),"ok":True}
        ]},
        {"title":"🧠 بوت التطوير", "rows":[
            {"label":"الحالة","value":web_status,"ok":web_status=="active"}
        ]},
        {"title":"🌐 الخدمات", "rows":[
            {"label":"Nginx","value":nginx_status,"ok":nginx_status=="active"},
            {"label":"API (8080)","value":"شغال" if get_service("dev-bot")!="unknown" else "?","ok":True}
        ]}
    ]

    log_lines = logs if logs else ["لا توجد سجلات"]
    return render_template_string(HTML, cards=cards, log_lines=log_lines, now=datetime.now().strftime("%H:%M:%S"))

if __name__ == "__main__":
    print("📊 لوحة المراقبة: http://127.0.0.1:8090")
    app.run(host="127.0.0.1", port=8090, debug=False)


