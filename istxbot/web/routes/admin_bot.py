"""
مسارات إدارة البوت — المستخدمين، الإرسال، webhook، الشبح، المشتركين
"""
import os
import asyncio
import secrets
import subprocess
from datetime import datetime, timedelta

from ..common import (
    db, logger, BOT_TOKEN, ADMIN_PATH, DOWNLOAD_DIR, APP_DIR, BASE_DIR,
    DEFAULT_PLATFORM,
    _require_admin, _require_bot_admin,
    get_wp_option, get_daily_download_limit,
    http_requests,
)

bot_bp = Blueprint('admin_bot', __name__)


@bot_bp.before_request
def _before_bot_request():
    # العمليات المشتركة في before_request الرئيسي بـ app.py
    pass


# ═══ Bot Broadcast ═══

@bot_bp.route('/api/admin/bot-broadcast', methods=['POST'])
def admin_bot_broadcast():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح - الرجاء تسجيل الدخول"}), 401
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    token = (data.get('token') or BOT_TOKEN).strip()

    if not message:
        return jsonify({"success": False, "message": "الرجاء إدخال نص الرسالة"}), 400
    if not token:
        return jsonify({"success": False, "message": "لم يتم تعيين توكن البوت"}), 400

    try:
        visitors = asyncio.run(db.get_all_visitors(limit=2000))
        if not visitors:
            return jsonify({"success": False, "message": "لا يوجد مستخدمين لإرسال الرسالة"})

        success = 0
        failed = 0
        url = f"https://api.telegram.org/bot{token}/sendMessage"

        for v in visitors:
            uid = v.get('user_id')
            if not uid:
                continue
            try:
                resp = http_requests.post(url, json={
                    "chat_id": int(uid),
                    "text": f"📢 {message}",
                    "parse_mode": "HTML"
                }, timeout=10)
                if resp.status_code == 200:
                    success += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        return jsonify({
            "success": True,
            "message": f"تم الإرسال: {success} ناجح, {failed} فشل من أصل {len(visitors)}"
        })
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        return jsonify({"success": False, "message": f"خطأ: {str(e)[:100]}"}), 500


# ═══ Bot Webhook Control ═══

@bot_bp.route('/api/admin/bot-set-webhook', methods=['POST'])
def admin_bot_set_webhook():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح - يرجى تسجيل الدخول من صفحة تسجيل الدخول"}), 401
    data = request.get_json(silent=True) or {}
    webhook_url = (data.get('url') or '').strip()
    token = (data.get('token') or BOT_TOKEN).strip()

    if not webhook_url:
        return jsonify({"success": False, "message": "الرجاء إدخال رابط Webhook"}), 400
    if not token:
        return jsonify({"success": False, "message": "لم يتم تعيين توكن البوت"}), 400

    try:
        url = f"https://api.telegram.org/bot{token}/setWebhook"
        resp = http_requests.post(url, json={"url": webhook_url}, timeout=15)
        result = resp.json()
        if result.get('ok'):
            return jsonify({"success": True, "message": f"✅ تم تعيين Webhook:\n{webhook_url}"})
        return jsonify({"success": False, "message": result.get('description', 'فشل التعيين')})
    except Exception as e:
        logger.error(f"Set webhook error: {e}")
        return jsonify({"success": False, "message": f"خطأ: {str(e)[:100]}"}), 500


@bot_bp.route('/api/admin/bot-info', methods=['POST'])
def admin_bot_info():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح - يرجى تسجيل الدخول من صفحة تسجيل الدخول"}), 401
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or BOT_TOKEN).strip()

    if not token:
        return jsonify({"success": False, "message": "لم يتم تعيين توكن البوت"}), 400

    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        resp = http_requests.get(url, timeout=10)
        result = resp.json()
        if not result.get('ok'):
            return jsonify({"success": False, "message": result.get('description', 'فشل الاتصال')})

        bot_data = result.get('result', {})
        stats = asyncio.run(db.get_admin_stats())

        return jsonify({
            "success": True,
            "name": bot_data.get('first_name', ''),
            "username": bot_data.get('username', ''),
            "running": True,
            "users_count": stats.get('total_users', 0),
            "downloads_today": stats.get('downloads_today', 0),
            "total_downloads": stats.get('total_downloads', 0)
        })
    except Exception as e:
        logger.error(f"Bot info error: {e}")
        return jsonify({"success": False, "message": f"خطأ: {str(e)[:100]}"}), 500


@bot_bp.route('/api/admin/bot-webhook-info', methods=['POST'])
def admin_bot_webhook_info():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or BOT_TOKEN).strip()

    if not token:
        return jsonify({"success": False, "message": "لم يتم تعيين توكن البوت"}), 400

    try:
        url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
        resp = http_requests.get(url, timeout=10)
        result = resp.json()
        if not result.get('ok'):
            return jsonify({"success": False, "message": result.get('description', 'فشل')})

        wh = result.get('result', {})
        return jsonify({
            "success": True,
            "url": wh.get('url', ''),
            "has_custom_certificate": wh.get('has_custom_certificate', False),
            "pending_update_count": wh.get('pending_update_count', 0),
            "last_error_date": wh.get('last_error_date', 0),
            "last_error_message": wh.get('last_error_message', ''),
            "max_connections": wh.get('max_connections', 0),
        })
    except Exception as e:
        logger.error(f"Webhook info error: {e}")
        return jsonify({"success": False, "message": f"خطأ: {str(e)[:100]}"}), 500


@bot_bp.route('/api/admin/bot-delete-webhook', methods=['POST'])
def admin_bot_delete_webhook():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or BOT_TOKEN).strip()

    if not token:
        return jsonify({"success": False, "message": "لم يتم تعيين توكن البوت"}), 400

    try:
        url = f"https://api.telegram.org/bot{token}/deleteWebhook"
        resp = http_requests.post(url, timeout=10)
        result = resp.json()
        if result.get('ok'):
            return jsonify({"success": True, "message": "✅ تم حذف Webhook بنجاح - البوت سيعمل بوضع Polling"})
        return jsonify({"success": False, "message": result.get('description', 'فشل الحذف')})
    except Exception as e:
        logger.error(f"Delete webhook error: {e}")
        return jsonify({"success": False, "message": f"خطأ: {str(e)[:100]}"}), 500


@bot_bp.route('/api/admin/bot-settings', methods=['POST'])
def admin_bot_settings():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    wp_keys = [
        'tk_bot_token', 'tk_bot_enabled', 'tk_bot_webhook_url', 'tk_bot_admin_ids',
        'tk_bot_admin_name', 'tk_bot_admin_bio',
        'tk_bot_start_message', 'tk_bot_help_message', 'tk_bot_ads_message',
        'tk_bot_ads_interval', 'tk_bot_force_channels', 'tk_bot_free_downloads',
        'tk_bot_max_file_size', 'tk_bot_watermark', 'tk_bot_welcome_image',
        'tk_bot_supported_platforms'
    ]

    settings = {key: get_wp_option(key, '') for key in wp_keys}
    return jsonify({"success": True, "settings": settings, "synced_at": datetime.now().isoformat()})


# ═══ Bot Users Management ═══

@bot_bp.route('/api/admin/bot-users', methods=['POST'])
def admin_bot_users():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    limit = int(data.get('limit', 100))
    page = int(data.get('page', 1))
    search = (data.get('search') or '').strip().lower()
    filter_country = (data.get('country') or '').strip()

    try:
        all_visitors = asyncio.run(db.get_all_visitors(limit=2000))
        stats = asyncio.run(db.get_admin_stats())

        banned_file = os.path.join(BASE_DIR, 'banned_users.txt')
        banned = set()
        if os.path.exists(banned_file):
            with open(banned_file) as f:
                banned = set(int(x) for x in f.read().strip().split('\n') if x.strip())

        filtered = []
        for v in all_visitors:
            uid = v.get('user_id', 0)
            v['is_banned'] = uid in banned
            name = (v.get('first_name', '') + ' ' + (v.get('last_name', '') or '')).lower()
            uname = (v.get('username', '') or '').lower()
            sid = str(uid)

            if search and not (search in name or search in uname or search in sid):
                continue
            if filter_country and v.get('country', '') != filter_country:
                continue

            v['language_code'] = v.get('language_code', '')
            filtered.append(v)

        total = len(filtered)
        start = (page - 1) * limit
        page_users = filtered[start:start + limit]

        countries = list(set(v.get('country', 'غير معروف') for v in all_visitors if v.get('country')))

        return jsonify({
            "success": True,
            "users": page_users,
            "total": total,
            "pages": max(1, (total + limit - 1) // limit) if total else 0,
            "page": page,
            "total_all": stats.get('total_users', 0),
            "monthly": stats.get('monthly_users', 0),
            "banned_count": len(banned),
            "countries": sorted(countries)
        })
    except Exception as e:
        logger.error(f"Bot users error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@bot_bp.route('/api/admin/bot-users-export', methods=['POST'])
def admin_bot_users_export():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    try:
        visitors = asyncio.run(db.get_all_visitors(limit=5000))
        import csv, io
        output = io.StringIO()
        w = csv.writer(output)
        w.writerow(['user_id', 'first_name', 'last_name', 'username', 'country', 'language', 'visit_count', 'first_visit', 'last_visit', 'is_premium'])
        for v in visitors:
            w.writerow([
                v.get('user_id', ''), v.get('first_name', ''), v.get('last_name', ''),
                v.get('username', ''), v.get('country', ''), v.get('language_code', ''),
                v.get('visit_count', ''), v.get('first_visit', ''), v.get('last_visit', ''),
                v.get('is_premium', 0)
            ])
        return Response(output.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment;filename=bot_users.csv"})
    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@bot_bp.route('/api/admin/bot-user-action', methods=['POST'])
def admin_bot_user_action():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    action = (data.get('action') or '').strip()
    target_id = int(data.get('user_id', 0))
    ids = data.get('user_ids', [])
    value = data.get('value', '').strip()

    banned_file = os.path.join(BASE_DIR, 'banned_users.txt')

    def _load_banned():
        if os.path.exists(banned_file):
            with open(banned_file) as f:
                return set(int(x) for x in f.read().strip().split('\n') if x.strip())
        return set()

    def _save_banned(b):
        with open(banned_file, 'w') as f:
            f.write('\n'.join(str(x) for x in b) if b else '')

    try:
        if action == 'bulk_ban' and ids:
            banned = _load_banned()
            banned.update(int(i) for i in ids)
            _save_banned(banned)
            return jsonify({"success": True, "message": f"تم حظر {len(ids)} مستخدم"})

        elif action == 'bulk_delete' and ids:
            deleted = 0
            for uid in ids:
                ok = asyncio.run(db.delete_visitor(int(uid)))
                if ok:
                    deleted += 1
            return jsonify({"success": True, "message": f"تم حذف {deleted} مستخدم"})

        if not target_id:
            return jsonify({"success": False, "message": "معرف المستخدم مطلوب"}), 400

        if action == 'ban':
            banned = _load_banned()
            banned.add(target_id)
            _save_banned(banned)
            return jsonify({"success": True, "message": f"تم حظر المستخدم {target_id}"})

        elif action == 'unban':
            banned = _load_banned()
            banned.discard(target_id)
            _save_banned(banned)
            return jsonify({"success": True, "message": f"تم إلغاء حظر المستخدم {target_id}"})

        elif action == 'delete_user':
            ok = asyncio.run(db.delete_visitor(target_id))
            return jsonify({"success": ok, "message": "تم حذف المستخدم" if ok else "فشل الحذف"})

        elif action == 'set_points':
            points = int(data.get('value', 0))
            asyncio.run(db.update_user(target_id, points=points))
            return jsonify({"success": True, "message": f"تم تحديث النقاط للمستخدم {target_id}"})

        elif action == 'set_tier':
            tier = value
            asyncio.run(db.update_user(target_id, tier=tier))
            return jsonify({"success": True, "message": f"تم تغيير مستوى المستخدم {target_id} إلى {tier}"})

        elif action == 'bulk_set_tier' and ids:
            tier = value
            updated = 0
            for uid in ids:
                ok = asyncio.run(db.update_user(int(uid), tier=tier))
                if ok:
                    updated += 1
            return jsonify({"success": True, "message": f"تم تغيير مستوى {updated} مستخدم"})

        else:
            return jsonify({"success": False, "message": f"إجراء غير معروف: {action}"}), 400

    except Exception as e:
        logger.error(f"User action error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@bot_bp.route('/api/admin/bot-user-detail', methods=['POST'])
def admin_bot_user_detail():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    user_id = int(data.get('user_id', 0))
    if not user_id:
        return jsonify({"success": False, "message": "معرف المستخدم مطلوب"}), 400

    try:
        user = asyncio.run(db.get_visitor(user_id))
        downloads = asyncio.run(db.get_user_downloads(user_id, limit=50))
        points = asyncio.run(db.get_user_points(user_id))
        banned_file = os.path.join(BASE_DIR, 'banned_users.txt')
        banned = set()
        if os.path.exists(banned_file):
            with open(banned_file) as f:
                banned = set(int(x) for x in f.read().strip().split('\n') if x.strip())

        return jsonify({
            "success": True, "user": user, "downloads": downloads,
            "points": points or 0, "is_banned": user_id in banned
        })
    except Exception as e:
        logger.error(f"User detail error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@bot_bp.route('/api/admin/bot-user-activity', methods=['POST'])
def admin_bot_user_activity():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    user_id = int(data.get('user_id', 0))
    if not user_id:
        return jsonify({"success": False, "message": "معرف المستخدم مطلوب"}), 400

    try:
        downloads = asyncio.run(db.get_user_downloads(user_id, limit=100))
        daily = asyncio.run(db.get_daily_download_count(user_id))
        today_limit = asyncio.run(db.get_daily_limit(user_id))
        return jsonify({
            "success": True, "downloads": downloads,
            "daily_count": daily,
            "daily_limit": today_limit.get('daily_limit', 0) if today_limit else 0
        })
    except Exception as e:
        logger.error(f"User activity error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@bot_bp.route('/api/admin/send-message', methods=['POST'])
def admin_send_message():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    user_id = int(data.get('user_id', 0))
    message = (data.get('message') or '').strip()
    token = (data.get('token') or BOT_TOKEN).strip()

    if not user_id or not message:
        return jsonify({"success": False, "message": "معرف المستخدم والرسالة مطلوبان"}), 400

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = http_requests.post(url, json={
            "chat_id": user_id,
            "text": f"📩 {message}",
            "parse_mode": "HTML"
        }, timeout=10)
        if resp.status_code == 200:
            return jsonify({"success": True, "message": "تم إرسال الرسالة"})
        return jsonify({"success": False, "message": "فشل إرسال الرسالة"}), 500
    except Exception as e:
        logger.error(f"Send message error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@bot_bp.route('/api/admin/promote-user', methods=['POST'])
def admin_promote_user():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    user_id = int(data.get('user_id', 0))
    tier_map = {'free': 'premium', 'premium': 'vip', 'vip': 'pro', 'pro': 'pro'}
    if not user_id:
        return jsonify({"success": False, "message": "معرف المستخدم مطلوب"}), 400

    try:
        user = asyncio.run(db.get_user(user_id))
        current_tier = user.get('tier', 'free') if user else 'free'
        new_tier = tier_map.get(current_tier, 'premium')
        asyncio.run(db.update_user(user_id, tier=new_tier, clear_tier_expiry=True))
        return jsonify({"success": True, "message": f"تمت ترقية المستخدم إلى {new_tier}"})
    except Exception as e:
        logger.error(f"Promote user error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


# ═══ Ghost Mode ═══

@bot_bp.route('/api/admin/ghost-set-tier', methods=['POST'])
def admin_ghost_set_tier():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    data = request.get_json(silent=True) or {}
    user_id = int(data.get('user_id', 0))
    new_tier = (data.get('tier') or '').strip().lower()
    expires_in = data.get('expires_in')

    if not user_id:
        return jsonify({"success": False, "message": "معرف المستخدم مطلوب"}), 400
    if not new_tier:
        return jsonify({"success": False, "message": "المستوى الجديد مطلوب"}), 400

    valid_tiers = ('free', 'premium', 'vip', 'pro')
    if new_tier not in valid_tiers:
        return jsonify({"success": False, "message": f"مستوى غير صالح. المستويات المتاحة: {', '.join(valid_tiers)}"}), 400

    try:
        user = asyncio.run(db.get_user(user_id))
        if not user:
            return jsonify({"success": False, "message": "المستخدم غير موجود"}), 404

        old_tier = (user.get('tier') or 'free').lower()

        tier_expires_at = None
        expires_in_int = None
        clear_expiry = False
        if expires_in and int(expires_in) > 0:
            expires_in_int = int(expires_in)
            tier_expires_at = (datetime.now() + timedelta(seconds=expires_in_int)).isoformat()
        else:
            clear_expiry = True

        asyncio.run(db.update_user(
            user_id=user_id, tier=new_tier.upper(),
            tier_expires_at=tier_expires_at, clear_tier_expiry=clear_expiry
        ))

        admin_token = request.headers.get('X-Admin-Token', '')
        asyncio.run(db.log_ghost_action(
            admin_token=admin_token, user_id=user_id,
            old_tier=old_tier, new_tier=new_tier, expires_in=expires_in_int
        ))

        direction = ("ترقية" if valid_tiers.index(new_tier) > valid_tiers.index(old_tier) else
                     ("إنزال" if valid_tiers.index(new_tier) < valid_tiers.index(old_tier) else "تعديل"))
        return jsonify({
            "success": True,
            "message": f"تم {direction} المستخدم {user_id} من {old_tier} إلى {new_tier} (وضع الشبح)",
            "old_tier": old_tier, "new_tier": new_tier, "direction": direction
        })
    except Exception as e:
        logger.error(f"Ghost set tier error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@bot_bp.route('/api/admin/ghost-get-history', methods=['POST'])
def admin_ghost_get_history():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    limit = int(data.get('limit', 50))

    try:
        actions = asyncio.run(db.get_ghost_actions(
            limit=min(limit, 200),
            user_id=int(user_id) if user_id else None
        ))
        return jsonify({"success": True, "actions": actions, "total": len(actions)})
    except Exception as e:
        logger.error(f"Ghost history error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


# ═══ Subscribers Management ═══

@bot_bp.route('/api/admin/bot-subscribers', methods=['POST'])
def admin_bot_subscribers():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    search = (data.get('search') or '').strip().lower()

    try:
        new_requests = asyncio.run(db.get_subscription_requests("new"))
        active_requests = asyncio.run(db.get_subscription_requests("active"))

        subscribers = []
        for r in new_requests:
            r['status_label'] = 'قيد المراجعة'
            r['status_class'] = 'pending'
            r['keys'] = []
            email = r.get('email', '')
            if email:
                keys = asyncio.run(db.find_keys_by_owner(email))
                r['keys'] = keys if keys else []
            subscribers.append(r)
        for r in active_requests:
            r['status_label'] = 'مفعل'
            r['status_class'] = 'active'
            r['keys'] = []
            email = r.get('email', '')
            if email:
                keys = asyncio.run(db.find_keys_by_owner(email))
                r['keys'] = keys if keys else []
            subscribers.append(r)

        if search:
            subscribers = [s for s in subscribers if search in (s.get('name', '') + s.get('email', '')).lower()]

        pending = sum(1 for s in subscribers if s.get('status') == 'new')
        active = sum(1 for s in subscribers if s.get('status') == 'active')

        return jsonify({
            "success": True, "subscribers": subscribers,
            "pending": pending, "active": active, "total": len(subscribers)
        })
    except Exception as e:
        logger.error(f"Subscribers error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@bot_bp.route('/api/admin/bot-subscriber-lookup', methods=['POST'])
def admin_bot_subscriber_lookup():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()

    if not email or '@' not in email:
        return jsonify({"success": False, "message": "بريد غير صحيح"}), 400

    try:
        keys = asyncio.run(db.find_keys_by_owner(email))

        sub_info = None
        for status in ['new', 'active', 'dismissed']:
            subs = asyncio.run(db.get_subscription_requests(status))
            for s in subs:
                if s.get('email') == email:
                    sub_info = s
                    break
            if sub_info:
                break

        total_usage = sum(int(k.get('usage_count', 0)) for k in keys) if keys else 0
        total_limit = sum(int(k.get('usage_limit', 0)) for k in keys) if keys else 0

        return jsonify({
            "success": True, "found": bool(sub_info or keys),
            "email": email, "subscription": sub_info,
            "keys": keys, "keys_count": len(keys) if keys else 0,
            "total_usage": total_usage, "total_limit": total_limit,
        })
    except Exception as e:
        logger.error(f"Subscriber lookup error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@bot_bp.route('/api/admin/bot-subscriber-action', methods=['POST'])
def admin_bot_subscriber_action():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    action = (data.get('action') or '').strip()
    sub_id = int(data.get('id', 0))
    email = (data.get('email') or '').strip().lower()
    limit = int(data.get('limit', 50))
    platform = (data.get('platform') or 'TikTok').strip()
    note = (data.get('note') or '').strip()

    if not action:
        return jsonify({"success": False, "message": "بيانات غير مكتملة"}), 400

    try:
        if action == 'activate':
            KEY_PREFIXES = {"TikTok": "ttk-"}
            prefix = KEY_PREFIXES.get(platform, "k-")
            key = prefix + secrets.token_hex(4)
            ok = asyncio.run(db.create_activation_key(key=key, owner_name=email, usage_limit=limit, notes="اشتراك مفعل عبر لوحة البوت", platform=platform))
            if ok:
                asyncio.run(db.update_subscription_status(sub_id, "active"))
                return jsonify({"success": True, "message": f"تم تفعيل الاشتراك", "key": key})

        elif action == 'dismiss':
            asyncio.run(db.update_subscription_status(sub_id, "dismissed"))
            return jsonify({"success": True, "message": "تم رفض الطلب"})

        elif action == 'update_limit' and email:
            keys = asyncio.run(db.find_keys_by_owner(email))
            updated = 0
            for k in keys:
                ok = asyncio.run(db.update_activation_key(k['key'], usage_limit=limit))
                if ok:
                    updated += 1
            return jsonify({"success": True, "message": f"تم تحديث {updated} مفتاح", "updated": updated})

        elif action == 'create_key':
            KEY_PREFIXES = {"TikTok": "ttk-"}
            prefix = KEY_PREFIXES.get(platform, "k-")
            key = prefix + secrets.token_hex(4)
            ok = asyncio.run(db.create_activation_key(key=key, owner_name=email, usage_limit=limit, notes=note or "مفتاح يدوي", platform=platform))
            if ok:
                return jsonify({"success": True, "message": f"تم إنشاء مفتاح للمشترك", "key": key})
            return jsonify({"success": False, "message": "فشل إنشاء المفتاح"}), 500

        elif action == 'delete_key':
            key_val = (data.get('key') or '').strip()
            if key_val:
                ok = asyncio.run(db.delete_activation_key(key_val))
                return jsonify({"success": ok, "message": "تم حذف المفتاح" if ok else "فشل الحذف"})

        else:
            return jsonify({"success": False, "message": f"إجراء غير معروف: {action}"}), 400

    except Exception as e:
        logger.error(f"Subscriber action error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


# ═══ Bot Restart ═══

@bot_bp.route('/api/admin/bot-restart', methods=['POST'])
def admin_bot_restart():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    try:
        result = subprocess.run(['sudo', 'systemctl', 'restart', 'download-bot.service'],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info("Bot service restarted via admin panel")
            return jsonify({"success": True, "message": "✅ تم إعادة تشغيل البوت بنجاح"})
        return jsonify({"success": False, "message": f"فشل: {result.stderr[:100]}"}), 500
    except Exception as e:
        logger.error(f"Bot restart error: {e}")
        return jsonify({"success": False, "message": f"خطأ: {str(e)[:100]}"}), 500


