"""
مسارات المشرف الأساسية — المصادقة، المفاتيح، الاشتراكات، الإحصائيات، إعدادات الموقع، الرفع
"""
import os

import asyncio
import hashlib
import secrets


from flask import Blueprint, render_template, request, jsonify, Response, g

from ..common import (
    db, logger, BOT_TOKEN, ADMIN_PATH, DOWNLOAD_DIR, APP_DIR, BASE_DIR,
    DEFAULT_PLATFORM,
    _ensure_db, _track_visitor,
    _require_admin, _require_bot_admin,
    send_subscription_email, get_wp_option,
)
from ..common import _PLATFORM_CONFIGS as PLATFORM_CONFIGS
from ..common import _DEFAULT_SITE_SETTINGS as DEFAULT_SITE_SETTINGS

admin_bp = Blueprint('admin', __name__)


@admin_bp.before_request
def _before_admin_request():
    # العمليات المشتركة في before_request الرئيسي بـ app.py
    g.platform = request.args.get('platform', DEFAULT_PLATFORM)


# ═══ Admin Page ═══

@admin_bp.route('/' + ADMIN_PATH)
def admin_page():
    return render_template('admin.html')


# ═══ Admin Auth ═══

@admin_bp.route('/api/admin/request-otp', methods=['POST'])
def admin_request_otp():
    data = request.get_json(silent=True) or {}
    user_id = int(data.get('user_id', 0) or os.getenv('ADMIN_ID', '0'))
    if not user_id:
        return jsonify({"success": False, "message": "معرف المستخدم مطلوب"}), 400
    otp = asyncio.run(db.create_otp(user_id))
    if otp:
        send_telegram_notification_safe(f"🔐 رمز التحقق: <code>{otp}</code>")
        return jsonify({"success": True, "message": "تم إرسال رمز التحقق"})
    return jsonify({"success": False, "message": "فشل إنشاء الرمز"}), 500


@admin_bp.route('/api/admin/verify-otp', methods=['POST'])
def admin_verify_otp():
    data = request.get_json(silent=True) or {}
    user_id = int(data.get('user_id', 0) or os.getenv('ADMIN_ID', '0'))
    otp_code = (data.get('otp') or '').strip()
    if not user_id or not otp_code:
        return jsonify({"success": False, "message": "بيانات غير مكتملة"}), 400
    result = asyncio.run(db.verify_otp(user_id, otp_code))
    if result.get('success'):
        token = asyncio.run(db.create_session(user_id))
        return jsonify({"success": True, "token": token})
    return jsonify(result), 401


@admin_bp.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    return jsonify({"success": True})


@admin_bp.route('/api/admin/check-session', methods=['GET'])
def admin_check_session():
    if not _require_admin():
        return jsonify({"success": False}), 401
    return jsonify({"success": True})


@admin_bp.route('/api/admin/change-password', methods=['POST'])
def admin_change_password():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    password = (data.get('password') or '').strip()
    if len(password) < 6:
        return jsonify({"success": False, "message": "كلمة المرور 6 أحرف على الأقل"})
    new_hash = hashlib.sha256(password.encode()).hexdigest()
    env_path = os.path.join(BASE_DIR, '.env')
    try:
        with open(env_path, 'r') as f:
            content = f.read()
        if 'ADMIN_PASSWORD_HASH' in content:
            content = os.linesep.join([
                line if not line.startswith('ADMIN_PASSWORD_HASH=') else f'ADMIN_PASSWORD_HASH={new_hash}'
                for line in content.splitlines()
            ])
        else:
            content += f'\nADMIN_PASSWORD_HASH={new_hash}\n'
        tmp_path = env_path + '.tmp'
        with open(tmp_path, 'w') as f:
            f.write(content)
        os.replace(tmp_path, env_path)
        return jsonify({"success": True, "message": "تم تغيير كلمة المرور بنجاح"})
    except Exception as e:
        logger.error(f"Error writing password: {e}")
        return jsonify({"success": False, "message": "حدث خطأ في حفظ كلمة المرور"}), 500


# ═══ Dashboard & Stats ═══

@admin_bp.route('/api/admin/stats', methods=['POST'])
def admin_stats():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    stats = asyncio.run(db.get_admin_stats())
    return jsonify({"success": True, **stats})


@admin_bp.route('/api/admin/dashboard', methods=['POST'])
def admin_dashboard():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    stats = asyncio.run(db.get_dashboard_stats())
    return jsonify({"success": True, **stats})


@admin_bp.route('/api/admin/visitor-stats', methods=['POST'])
def admin_visitor_stats():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    stats = asyncio.run(db.get_web_visitor_stats())
    recent = asyncio.run(db.get_recent_web_visitors(30))
    return jsonify({"success": True, "stats": stats, "recent": recent})


# ═══ Key Management ═══

@admin_bp.route('/api/admin/keys', methods=['POST'])
def admin_keys():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    keys = asyncio.run(db.get_all_activation_keys())
    return jsonify({"success": True, "keys": keys})


@admin_bp.route('/api/admin/create-keys', methods=['POST'])
def admin_create_keys():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    owner = data.get('owner', '').strip().lower()
    limit = int(data.get('limit', 10))
    count = int(data.get('count', 1))
    notes = data.get('notes', '').strip()
    platform = data.get('platform', 'TikTok').strip()

    KEY_PREFIXES = {"TikTok": "ttk-"}

    async def _create():
        created = []
        for _ in range(count):
            prefix = KEY_PREFIXES.get(platform, "k-")
            key = prefix + secrets.token_hex(4)
            ok = await db.create_activation_key(key=key, owner_name=owner, usage_limit=limit, notes=notes, platform=platform)
            if ok:
                created.append(key)
        return created

    keys = asyncio.run(_create())
    if keys:
        if owner and '@' in owner:
            try:
                key_list_html = ''.join(
                    f'<div style="background:#16213e;border:1px solid #2a2a4a;border-radius:8px;padding:12px;margin:8px 0;direction:ltr;font-family:monospace;font-size:16px;color:#fff;text-align:center">🔑 {k}</div>'
                    for k in keys)
                platform_name = {"TikTok": "TikTok"}.get(platform, platform)
                body_html = f"""<html dir="rtl"><body style="font-family:Arial,sans-serif;background:#0f0f0f;color:#e0e0e0;padding:20px">
<div style="max-width:420px;margin:0 auto;background:#1a1a2e;border-radius:12px;padding:24px;text-align:center">
<h2 style="color:#fe2c55">✅ تم إنشاء مفتاح {platform_name}</h2>
<p style="color:#ccc;font-size:14px;line-height:1.8">مرحباً، مفتاح التفعيل الخاص بك لمنصة {platform_name}:</p>
{key_list_html}
<div style="background:rgba(254,44,85,0.08);border-radius:8px;padding:12px;margin-top:12px">
<p style="color:#888;font-size:13px;margin:0">📊 حد التحميلات: <b style="color:#fff">{limit}</b></p>
<p style="color:#888;font-size:13px;margin:4px 0 0">🔗 رابط التحميل: <a href="https://{platform.lower()}.istx.io" style="color:#25f4ee">https://{platform.lower()}.istx.io</a></p>
</div></div></body></html>"""
                send_subscription_email(owner, f"مفتاح تفعيل {platform_name} - istx.io", body_html)
                logger.info(f"Key email sent to {owner} for {platform}")
            except Exception as e:
                logger.error(f"Failed to send key email: {e}")
        return jsonify({"success": True, "message": f"تم إنشاء {len(keys)} مفتاح لـ {platform}", "keys": keys})
    return jsonify({"success": False, "message": "فشل إنشاء المفاتيح"}), 500


@admin_bp.route('/api/admin/toggle-key', methods=['POST'])
def admin_toggle_key():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    asyncio.run(db.toggle_activation_key(data.get('key', ''), bool(data.get('active', True))))
    return jsonify({"success": True})


@admin_bp.route('/api/admin/delete-key', methods=['POST'])
def admin_delete_key():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    asyncio.run(db.delete_activation_key(data.get('key', '')))
    return jsonify({"success": True})


@admin_bp.route('/api/admin/update-key', methods=['POST'])
def admin_update_key():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    key = data.get('key', '').strip()
    count = int(data.get('usage_count')) if data.get('usage_count') is not None else None
    limit = int(data.get('usage_limit')) if data.get('usage_limit') is not None else None
    if not key or (count is None and limit is None):
        return jsonify({"success": False, "message": "بيانات غير مكتملة"}), 400
    ok = asyncio.run(db.update_activation_key(key, usage_count=count, usage_limit=limit))
    return jsonify({"success": ok, "message": "تم التحديث" if ok else "حدث خطأ"})


@admin_bp.route('/api/admin/search-keys', methods=['POST'])
def admin_search_keys():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    query = data.get('query', '').strip()
    platform = data.get('platform', '').strip()
    keys = asyncio.run(db.search_keys(query=query, platform=platform))
    return jsonify({"success": True, "keys": keys})


@admin_bp.route('/api/admin/export-keys', methods=['POST'])
def admin_export_keys():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    csv_data = asyncio.run(db.export_keys_csv())
    return Response(csv_data, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=keys_export.csv"})


# ═══ Subscriptions ═══

@admin_bp.route('/api/admin/subscriptions', methods=['POST'])
def admin_subscriptions():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    requests_list = asyncio.run(db.get_subscription_requests("new"))
    return jsonify({"success": True, "requests": requests_list})


@admin_bp.route('/api/admin/activate-subscription', methods=['POST'])
def admin_activate_subscription():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    limit = int(data.get('limit', 50))
    req_id = int(data.get('id', 0))
    platform = data.get('platform', 'TikTok').strip()

    KEY_PREFIXES = {"TikTok": "ttk-"}
    prefix = KEY_PREFIXES.get(platform, "k-")
    key = prefix + secrets.token_hex(4)

    async def _activate():
        ok = await db.create_activation_key(key=key, owner_name=email, usage_limit=limit, notes="اشتراك مفعل", platform=platform)
        if ok and req_id:
            await db.update_subscription_status(req_id, "active")
        return ok

    ok = asyncio.run(_activate())
    if ok:
        accent = '#fe2c55'
        domain = f"{platform.lower()}.istx.io"
        platform_name = {"TikTok": "TikTok"}.get(platform, platform)
        key_html = f"""<html dir="rtl"><body style="font-family:Arial,sans-serif;background:#0f0f0f;color:#e0e0e0;padding:20px">
<div style="max-width:420px;margin:0 auto;background:#1a1a2e;border-radius:12px;padding:24px;text-align:center">
<h2 style="color:{accent}">✅ تم تفعيل اشتراكك - {platform_name}</h2>
<p style="color:#ccc;font-size:14px;line-height:1.8">شكراً لاشتراكك. مفتاح التفعيل الخاص بك لمنصة {platform_name}:</p>
<div style="background:#16213e;border:1px solid #2a2a4a;border-radius:10px;padding:16px;margin:16px 0">
<span style="font-family:monospace;font-size:20px;font-weight:800;color:#fff;letter-spacing:2px;direction:ltr;display:inline-block">🔑 {key}</span>
</div>
<p style="color:#888;font-size:13px;line-height:1.7">عدد التحميلات: <b style="color:#fff">{limit}</b></p>
<a href="https://{domain}" style="display:inline-block;margin-top:12px;padding:12px 28px;background:{accent};color:#000;text-decoration:none;border-radius:8px;font-weight:700;font-size:14px">📥 ابدأ التحميل</a>
</div></body></html>"""
        send_subscription_email(email, f"تم تفعيل اشتراكك - مفتاح: {key}", key_html)
        return jsonify({"success": True, "message": f"تم تفعيل الاشتراك وإرسال المفتاح إلى {email}", "key": key, "email": email})
    return jsonify({"success": False, "message": "حدث خطأ"}), 500


@admin_bp.route('/api/admin/dismiss-subscription', methods=['POST'])
def admin_dismiss_subscription():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    asyncio.run(db.update_subscription_status(int(data.get('id', 0)), "done"))
    return jsonify({"success": True})


# ═══ Site Settings ═══

@admin_bp.route('/api/admin/site-settings', methods=['POST'])
def admin_site_settings():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    platform = data.get('platform', '')
    prefix = f"{platform}:" if platform else ""

    if 'settings' in data:
        saved = 0
        for key, value in data['settings'].items():
            if not isinstance(value, str):
                continue
            db_key = prefix + key
            ok = asyncio.run(db.set_site_setting(db_key, value))
            if ok:
                saved += 1
        return jsonify({"success": True, "message": f"تم حفظ {saved} إعداد لـ {platform or 'العامة'}"})

    settings_dict = asyncio.run(db.get_all_site_settings())
    result = {}
    for k, v in settings_dict.items():
        if platform:
            if k.startswith(prefix):
                result[k[len(prefix):]] = v
        else:
            if not k.startswith('TikTok:'):
                result[k] = v
    if platform:
        defaults = PLATFORM_CONFIGS.get(platform, {})
        merged = {**defaults, **result}
        return jsonify({"success": True, "settings": merged, "platform": platform})
    else:
        merged = {**DEFAULT_SITE_SETTINGS, **result}
        return jsonify({"success": True, "settings": merged, "platform": "global"})


@admin_bp.route('/api/admin/ads-settings', methods=['POST'])
def admin_ads_settings():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    if 'settings' in data:
        saved = 0
        for k, v in data['settings'].items():
            ok = asyncio.run(db.set_site_setting(f"ads:{k}", str(v)))
            if ok:
                saved += 1
        return jsonify({"success": True, "message": f"تم حفظ {saved} إعداد إعلاني"})
    all_settings = asyncio.run(db.get_all_site_settings())
    ads_settings = {k[4:]: v for k, v in all_settings.items() if k.startswith("ads:")}
    return jsonify({"success": True, "settings": ads_settings})


@admin_bp.route('/api/admin/landing-page', methods=['POST'])
def admin_landing_page():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    if 'settings' in data:
        saved = 0
        for k, v in data['settings'].items():
            ok = asyncio.run(db.set_landing_page_setting(k, v))
            if ok:
                saved += 1
        return jsonify({"success": True, "message": f"تم حفظ {saved} إعداد للصفحة الرئيسية"})
    settings = asyncio.run(db.get_landing_page_settings())
    return jsonify({"success": True, "settings": settings})


# ═══ File Uploads ═══

def _save_uploaded_file(file, prefix, static_dir):
    """Helper: save uploaded file with allowed extension check"""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif'):
        return None, "الصيغ المسموحة: png, jpg, svg, webp, gif"
    filename = f"{prefix}{ext}"
    save_path = os.path.join(static_dir, filename)
    file.save(save_path)
    return f"/static/{filename}", None


def _delete_custom_file(prefix, static_dir):
    """Helper: delete all variants of a custom uploaded file"""
    for ext in ('.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif'):
        path = os.path.join(static_dir, f"{prefix}{ext}")
        if os.path.exists(path):
            os.remove(path)


@admin_bp.route('/api/admin/upload-logo', methods=['POST'])
def admin_upload_logo():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    if 'logo' not in request.files:
        return jsonify({"success": False, "message": "لم يتم إرسال ملف"}), 400
    file = request.files['logo']
    if not file or file.filename == '':
        return jsonify({"success": False, "message": "ملف فارغ"}), 400
    static_dir = os.path.join(APP_DIR, 'static')
    url, error = _save_uploaded_file(file, 'logo_custom', static_dir)
    if error:
        return jsonify({"success": False, "message": error}), 400
    asyncio.run(db.set_site_setting('logo_url', url))
    asyncio.run(db.set_site_setting('logo_type', 'image' if not file.filename.endswith('.svg') else 'svg'))
    return jsonify({"success": True, "message": "تم رفع الشعار", "url": url})


@admin_bp.route('/api/admin/delete-logo', methods=['POST'])
def admin_delete_logo():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    _delete_custom_file('logo_custom', os.path.join(APP_DIR, 'static'))
    asyncio.run(db.set_site_setting('logo_url', ''))
    asyncio.run(db.set_site_setting('logo_type', 'svg'))
    return jsonify({"success": True, "message": "تم حذف الشعار واستعادة الافتراضي"})


@admin_bp.route('/api/admin/upload-banner-icon', methods=['POST'])
def admin_upload_banner_icon():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    if 'icon' not in request.files:
        return jsonify({"success": False, "message": "لم يتم إرسال ملف"}), 400
    file = request.files['icon']
    if not file or file.filename == '':
        return jsonify({"success": False, "message": "ملف فارغ"}), 400
    static_dir = os.path.join(APP_DIR, 'static')
    url, error = _save_uploaded_file(file, 'banner_icon_custom', static_dir)
    if error:
        return jsonify({"success": False, "message": error}), 400
    asyncio.run(db.set_site_setting('banner_icon_url', url))
    return jsonify({"success": True, "message": "تم رفع أيقونة البنر", "url": url})


@admin_bp.route('/api/admin/delete-banner-icon', methods=['POST'])
def admin_delete_banner_icon():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    _delete_custom_file('banner_icon_custom', os.path.join(APP_DIR, 'static'))
    asyncio.run(db.set_site_setting('banner_icon_url', ''))
    return jsonify({"success": True, "message": "تم حذف أيقونة البنر واستعادة الافتراضي"})


@admin_bp.route('/api/admin/upload-contact-icon', methods=['POST'])
def admin_upload_contact_icon():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    channel = request.form.get('channel', 'whatsapp')
    if channel not in ('whatsapp', 'telegram'):
        return jsonify({"success": False, "message": "قناة غير صالحة"}), 400
    if 'icon' not in request.files:
        return jsonify({"success": False, "message": "لم يتم إرسال ملف"}), 400
    file = request.files['icon']
    if not file or file.filename == '':
        return jsonify({"success": False, "message": "ملف فارغ"}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.png', '.jpg', '.jpeg', '.svg', '.webp'):
        return jsonify({"success": False, "message": "الصيغ المسموحة: png, jpg, svg, webp"}), 400
    static_dir = os.path.join(APP_DIR, 'static')
    icon_name = f"contact_{channel}{ext}"
    save_path = os.path.join(static_dir, icon_name)
    file.save(save_path)
    icon_url = f"/static/{icon_name}"
    asyncio.run(db.set_site_setting(f"contact_{channel}_icon", icon_url))
    return jsonify({"success": True, "message": f"تم رفع أيقونة {channel}", "url": icon_url})


@admin_bp.route('/api/admin/delete-contact-icon', methods=['POST'])
def admin_delete_contact_icon():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    channel = data.get('channel', 'whatsapp')
    if channel not in ('whatsapp', 'telegram'):
        return jsonify({"success": False, "message": "قناة غير صالحة"}), 400
    _delete_custom_file(f"contact_{channel}", os.path.join(APP_DIR, 'static'))
    asyncio.run(db.set_site_setting(f"contact_{channel}_icon", ''))
    return jsonify({"success": True, "message": f"تم حذف أيقونة {channel}"})


# ═══ Download Logs & Trends ═══

@admin_bp.route('/api/admin/download-logs', methods=['POST'])
def admin_download_logs():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    page = int(data.get('page', 1))
    platform = data.get('platform', '')
    result = asyncio.run(db.get_download_logs(page=page, platform=platform))
    return jsonify({"success": True, **result})


@admin_bp.route('/api/admin/download-trends', methods=['POST'])
def admin_download_trends():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    days = int(data.get('days', 14))
    trends = asyncio.run(db.get_download_trends(days))
    return jsonify({"success": True, "trends": trends})


# ═══ Helper ═══

def send_telegram_notification_safe(text: str):
    """Safe wrapper for sending Telegram notifications from admin routes"""
    try:
        from ..common import BOT_TOKEN as _BT, ADMIN_ID as _AI, send_telegram_notification as _stn
        _stn(text)
    except Exception:
        pass


