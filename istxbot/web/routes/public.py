"""
المسارات العامة — الصفحات الرئيسية و API العام (تحميل، مفاتيح، اشتراكات، مكافآت)
"""
import os
import asyncio
import secrets
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, send_file, after_this_request, g

# استيراد الحالة والمساعدات المشتركة
from ..common import (
    db, logger, BOT_TOKEN, ADMIN_PATH, DOWNLOAD_DIR, APP_DIR, BASE_DIR,
    _email_otp, DEFAULT_PLATFORM,
    _detect_platform, _get_platform_config, _get_downloader,
    _ensure_db, _track_visitor, _get_ads_settings, inject_site_settings,
    send_telegram_notification, send_email_otp, send_subscription_email,
    get_daily_download_limit,
)


public_bp = Blueprint('public', __name__)


# ═══ Before Request ═══

@public_bp.before_request
def _before_public_request():
    # تُنفذ العمليات المشتركة (ensure_db, track_visitor, detect_platform)
    # في before_request الرئيسي في app.py لتجنب التكرار
    g.platform = _detect_platform()


# ═══ Public Web Pages ═══

@public_bp.route('/')
def index():
    return render_template('index.html')


@public_bp.route('/health')
def health_check():
    try:
        asyncio.run(db.get_stats())
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)[:50]}"

    return jsonify({
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    })


@public_bp.route('/help')
def help_page():
    return render_template('help.html')


@public_bp.route('/contact')
def contact_page():
    return render_template('contact.html')


@public_bp.route('/account')
def account_page():
    return render_template('account.html')


@public_bp.route('/sw.js')
def service_worker():
    sw_path = os.path.join(APP_DIR, 'static', 'sw.js')
    if os.path.exists(sw_path):
        return send_file(sw_path, mimetype='application/javascript')
    return "// Service Worker not found", 404


# ═══ Download API ═══

# استيراد مؤجل لتجنب أخطاء aiogram في البيئات بدونها
_webhook_imports_done = False
_setup_bot = _process_update = _set_webhook = _get_bot = None


def _ensure_webhook_imports():
    """Lazy-load webhook dependencies to avoid ImportError if aiogram is not installed"""
    global _webhook_imports_done, _setup_bot, _process_update, _set_webhook, _get_bot
    if not _webhook_imports_done:
        from bot.webhook_setup import setup_bot, process_update, set_webhook, get_bot
        _setup_bot = setup_bot
        _process_update = process_update
        _set_webhook = set_webhook
        _get_bot = get_bot
        _webhook_imports_done = True


@public_bp.route('/api/bot/webhook', methods=['POST'])
def bot_webhook():
    _ensure_webhook_imports()
    if not _setup_bot():
        return jsonify({"ok": False, "description": "Bot not configured"}), 503
    try:
        _process_update(request.get_data())
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return jsonify({"ok": False, "description": str(e)[:200]}), 500


@public_bp.route('/api/download', methods=['POST'])
def api_download():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "بيانات غير صالحة"}), 400

    url = (data.get('url') or '').strip()
    key = (data.get('key') or '').strip()
    platform = g.get("platform", DEFAULT_PLATFORM)
    downloader = _get_downloader(platform)

    if not url:
        return jsonify({"success": False, "message": "الرجاء إدخال رابط الفيديو"}), 400

    # Validate key or provide free tier
    if not key:
        key_result = asyncio.run(db.validate_activation_key("__free_tier__", platform))
    else:
        key_result = asyncio.run(db.validate_activation_key(key, platform))

    if not key_result or not key_result.get('valid'):
        msg = key_result.get('message', 'مفتاح غير صالح') if key_result else 'مفتاح غير صالح'
        return jsonify({"success": False, "message": msg}), 403

    # Check daily limit
    daily_count = asyncio.run(db.get_daily_download_count(0))
    limit = get_daily_download_limit()
    if daily_count >= limit:
        return jsonify({"success": False, "message": f"تم تجاوز الحد اليومي ({limit} تحميلات)"}), 429

    # Process download
    try:
        result = asyncio.run(_process_download(url, key, platform))
        if result.get('success'):
            # Consume key usage
            if key and key != "__free_tier__":
                asyncio.run(db.consume_activation_key(key))

            # Record download
            asyncio.run(db.record_download(
                user_id=0, platform=platform,
                title=result.get('title', ''),
                file_size=result.get('file_size', 0),
                file_path=result.get('file_path', '')
            ))

            # Send notification
            try:
                send_telegram_notification(
                    f"📥 <b>تحميل جديد</b>\n"
                    f"المنصة: {platform}\n"
                    f"الرابط: {url[:80]}\n"
                    f"المفتاح: {key[:8]}..."
                )
            except Exception:
                pass

            # Clean up file after sending
            file_path = result.get('file_path', '')
            if file_path and os.path.exists(file_path):

                @after_this_request
                def cleanup(response):
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception:
                        pass
                    return response

                return send_file(
                    file_path, as_attachment=True,
                    download_name=result.get('filename', 'video.mp4')
                )
        else:
            return jsonify({
                "success": False,
                "message": result.get('error', 'فشل التحميل')
            }), 500
    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({"success": False, "message": f"خطأ: {str(e)[:100]}"}), 500


async def _process_download(url: str, key: str, platform: str = "TikTok") -> dict:
    """Process a download request asynchronously"""
    downloader = _get_downloader(platform)
    try:
        result = await downloader.download(url)
        # downloader.download() يرجع tuple: (success: bool, data: list|str, error: str)
        if isinstance(result, tuple):
            if len(result) >= 3:
                success, data, error = result[0], result[1], result[2]
                if success:
                    # البيانات قد تكون مسار ملف أو قائمة
                    file_path = data if isinstance(data, str) else (data[0] if data else None)
                    return {"success": True, "file_path": file_path, "filename": os.path.basename(file_path) if file_path else "video.mp4"}
                return {"success": False, "error": str(error) if error else "فشل التحميل"}
            return {"success": False, "error": "تنسيق نتيجة غير متوقع"}
        # لو كان dict (للتوافق مع downloaders الأخرى)
        if isinstance(result, dict):
            if result.get('success'):
                return result
            return {"success": False, "error": result.get('error', 'فشل التحميل')}
        return {"success": False, "error": "فشل التحميل"}
    except Exception as e:
        logger.error(f"Download processing error: {e}")
        return {"success": False, "error": str(e)[:200]}


# ═══ Key Management API ═══

@public_bp.route('/api/validate-key', methods=['POST'])
def api_validate_key():
    data = request.get_json(silent=True) or {}
    key = (data.get('key') or '').strip()
    platform = g.get("platform", DEFAULT_PLATFORM)

    if not key:
        return jsonify({"valid": False, "message": "الرجاء إدخال مفتاح التفعيل"}), 400

    result = asyncio.run(db.validate_activation_key(key, platform))
    return jsonify(result)


@public_bp.route('/api/free-key', methods=['POST'])
def api_free_key():
    """Generate a free trial key for the current platform"""
    platform = g.get("platform", DEFAULT_PLATFORM)
    key_prefix = "ttk-" if platform == "TikTok" else "k-"
    free_key = key_prefix + secrets.token_hex(4)

    ok = asyncio.run(db.create_activation_key(
        key=free_key, owner_name="مفتاح تجريبي", usage_limit=3,
        notes="تلقائي - تجربة مجانية", platform=platform
    ))
    if ok:
        return jsonify({"success": True, "key": free_key})
    return jsonify({"success": False, "message": "فشل إنشاء المفتاح"}), 500


@public_bp.route('/api/recover-key', methods=['POST'])
def api_recover_key():
    """Recover lost key using email OTP"""
    data = request.get_json(silent=True) or {}
    action = (data.get('action') or 'request').strip()
    email = (data.get('email') or '').strip().lower()

    if not email or '@' not in email:
        return jsonify({"success": False, "message": "بريد إلكتروني غير صالح"}), 400

    if action == 'request':
        # Generate and send OTP
        otp = ''.join(secrets.choice('0123456789') for _ in range(6))
        _email_otp[email] = {'otp': otp, 'expires': datetime.now().timestamp() + 300}
        ok = send_email_otp(email, otp)
        if ok:
            return jsonify({"success": True, "message": "تم إرسال رمز التحقق"})
        return jsonify({"success": False, "message": "فشل إرسال البريد - تواصل مع الدعم"}), 500

    elif action == 'verify':
        otp_code = (data.get('otp') or '').strip()
        stored = _email_otp.get(email, {})
        if not stored or stored.get('expires', 0) < datetime.now().timestamp():
            _email_otp.pop(email, None)
            return jsonify({"success": False, "message": "انتهت صلاحية الرمز"}), 400
        if stored.get('otp') != otp_code:
            return jsonify({"success": False, "message": "رمز غير صحيح"}), 400

        # Look up keys
        keys = asyncio.run(db.find_keys_by_owner(email))
        _email_otp.pop(email, None)
        return jsonify({
            "success": True,
            "keys": [{'key': k['key'], 'platform': k.get('platform','TikTok'),
                       'usage_limit': k.get('usage_limit',0), 'usage_count': k.get('usage_count',0)}
                      for k in keys] if keys else []
        })

    return jsonify({"success": False, "message": "إجراء غير معروف"}), 400


# ═══ Subscription API ═══

@public_bp.route('/api/subscribe', methods=['POST'])
def api_subscribe():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    platform = (data.get('platform') or g.get("platform", DEFAULT_PLATFORM)).strip()

    # Anti-bot: Honeypot
    if data.get('_honey', ''):
        return jsonify({"success": True, "message": "تم استلام الطلب"})

    # Anti-bot: Timing check
    timestamp = data.get('_t', 0)
    if timestamp and abs(datetime.now().timestamp() - int(timestamp)) < 3:
        return jsonify({"success": False, "message": "يرجى الانتظار"}), 400

    if not name or not email or '@' not in email:
        return jsonify({"success": False, "message": "الاسم والبريد مطلوبان"}), 400

    # Anti-duplicate
    async def _check_dup(e):
        for s in ['new', 'active']:
            subs = await db.get_subscription_requests(s)
            for sub in subs:
                if sub.get('email') == e:
                    return True
        return False

    if asyncio.run(_check_dup(email)):
        return jsonify({"success": False, "message": "يوجد طلب سابق لهذا البريد"}), 409

    ok = asyncio.run(db.add_subscription_request(name=name, email=email, platform=platform))
    if ok:
        send_telegram_notification(f"🆕 <b>طلب اشتراك جديد</b>\nالاسم: {name}\nالبريد: {email}\nالمنصة: {platform}")
        return jsonify({"success": True, "message": "تم استلام الطلب"})
    return jsonify({"success": False, "message": "حدث خطأ"}), 500


@public_bp.route('/api/subscription-status', methods=['POST'])
def api_subscription_status():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({"success": False, "message": "بريد غير صالح"}), 400

    async def _check():
        for status in ['active', 'new', 'dismissed']:
            subs = await db.get_subscription_requests(status)
            for s in subs:
                if s.get('email') == email:
                    return {'status': status, 'data': s}
        return None

    result = asyncio.run(_check())
    if result:
        return jsonify({"success": True, **result})
    return jsonify({"success": True, "status": "not_found"})


# ═══ Web Rewards / Points ═══

@public_bp.route('/api/web/get-reward-link', methods=['POST'])
def api_get_reward_link():
    data = request.get_json(silent=True) or {}
    user_id = int(data.get('user_id', 0))
    if not user_id:
        return jsonify({"success": False}), 400

    token = secrets.token_urlsafe(16)
    asyncio.run(db.create_reward_link(user_id=user_id, token=token))
    base = request.host_url.rstrip('/')
    return jsonify({"success": True, "url": f"{base}/reward/{token}"})


@public_bp.route('/reward/<token>')
def reward_landing(token):
    return render_template('reward.html', token=token)


@public_bp.route('/api/web/claim-reward', methods=['POST'])
def api_claim_reward():
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or '').strip()
    if not token:
        return jsonify({"success": False}), 400

    result = asyncio.run(db.claim_reward(token))
    return jsonify(result)


@public_bp.route('/api/web/points', methods=['POST'])
def api_web_points():
    data = request.get_json(silent=True) or {}
    user_id = int(data.get('user_id', 0))
    if not user_id:
        return jsonify({"points": 0})
    points = asyncio.run(db.get_user_points(user_id))
    return jsonify({"points": points})


@public_bp.route('/api/web/redeem-points', methods=['POST'])
def api_redeem_points():
    data = request.get_json(silent=True) or {}
    user_id = int(data.get('user_id', 0))
    if not user_id:
        return jsonify({"success": False}), 400

    result = asyncio.run(db.redeem_points(user_id))
    return jsonify(result)


