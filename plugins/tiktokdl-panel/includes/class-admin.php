<?php
namespace TikTokDL;

class Admin {

    private static $page_slug = 'tiktokdl-panel';

    public static function init() {
        add_action('admin_menu', [__CLASS__, 'add_menu']);
        add_action('admin_enqueue_scripts', [__CLASS__, 'enqueue']);
        // AJAX handlers
        add_action('wp_ajax_tdl_save_settings', [__CLASS__, 'ajax_save']);
        add_action('wp_ajax_tdl_scrape_test', [__CLASS__, 'ajax_scrape']);
        add_action('wp_ajax_tdl_health_check', [__CLASS__, 'ajax_health']);
        add_action('wp_ajax_tdl_send_push', [__CLASS__, 'ajax_push']);
    }

    public static function add_menu() {
        add_menu_page('إدارة TikTokDL', 'TikTokDL', 'manage_options', self::$page_slug, [__CLASS__, 'render'], 'dashicons-smartphone', 30);
    }

    public static function enqueue($hook) {
        if (strpos($hook, self::$page_slug) === false) return;
        wp_enqueue_style('tdl-admin', TDL_URL . 'assets/admin.css', [], TDL_VERSION . '.' . time());
        wp_enqueue_script('tdl-admin', TDL_URL . 'assets/admin.js', [], TDL_VERSION . '.' . time(), true);
        wp_localize_script('tdl-admin', 'TDL', [
            'ajax_url'  => admin_url('admin-ajax.php'),
            'nonce'     => wp_create_nonce('tdl_ajax_nonce'),
            'rest_url'  => rest_url('app/v1/health'),
            'api_key'   => TDL_API_KEY,
        ]);
    }

    // ============ AJAX Handlers ============

    public static function ajax_save() {
        check_ajax_referer('tdl_ajax_nonce');
        if (!current_user_can('manage_options')) wp_die(-1);

        $data = [];
        // Booleans
        $bools = ['maintenance_mode','force_update','download_enabled','background_download',
                   'hd_quality_enabled','mp3_conversion','ads_enabled','auto_clipboard','developer_mode'];
        foreach ($bools as $k) $data[$k] = !empty($_POST[$k]);

        // Integers
        foreach (['app_version','max_downloads_per_day'] as $k) 
            if (isset($_POST[$k])) $data[$k] = (int)$_POST[$k];

        // Strings
        $strings = ['maintenance_message','update_url','update_message','selector_video','selector_og',
                    'selector_jsonld','selector_regex','api_download_url','contact_email','telegram_bot',
                    'admob_app_id','admob_banner_id','admob_interstitial','developer_ids'];
        foreach ($strings as $k) if (isset($_POST[$k])) $data[$k] = sanitize_text_field($_POST[$k]);

        Settings::save($data);
        
        // Clear all caches
        delete_transient('tdl_api_config');
        $cache_file = TDL_DIR . 'data/config-cache.json';
        if (file_exists($cache_file)) unlink($cache_file);

        // Send real-time FCM notification to all devices
        if (FCM::is_ready()) {
            FCM::send_config_update();
        }

        wp_send_json_success(['message' => '✅ تم حفظ الإعدادات بنجاح']);
    }

    public static function ajax_scrape() {
        check_ajax_referer('tdl_ajax_nonce');
        if (!current_user_can('manage_options')) wp_die(-1);
        
        $url = sanitize_text_field($_POST['url'] ?? '');
        if (empty($url)) wp_send_json_error(['message' => 'الرجاء إدخال رابط TikTok']);
        
        $result = ScraperValidator::validate($url);
        wp_send_json_success($result);
    }

    public static function ajax_health() {
        check_ajax_referer('tdl_ajax_nonce');
        if (!current_user_can('manage_options')) wp_die(-1);
        
        $checks = [];
        $checks['wordpress'] = ['status' => 'ok', 'version' => get_bloginfo('version')];
        $checks['plugin'] = ['status' => 'ok', 'version' => TDL_VERSION];
        $checks['fcm'] = ['status' => FCM::is_ready() ? 'ok' : 'error'];
        $checks['storage'] = ['status' => is_writable(TDL_DIR . 'data') ? 'ok' : 'error'];
        $checks['download_api'] = ['status' => 'unknown', 'url' => Settings::get('api_download_url')];
        
        $all_ok = true;
        foreach ($checks as $c) if (($c['status'] ?? '') === 'error') $all_ok = false;
        
        wp_send_json_success(['success' => $all_ok, 'checks' => $checks, 'time' => current_time('mysql')]);
    }

    public static function ajax_push() {
        check_ajax_referer('tdl_ajax_nonce');
        if (!current_user_can('manage_options')) wp_die(-1);
        
        $title  = sanitize_text_field($_POST['title'] ?? '');
        $body   = sanitize_text_field($_POST['body'] ?? '');
        $url    = sanitize_text_field($_POST['url'] ?? '');
        $target = sanitize_text_field($_POST['target'] ?? 'all');

        if (empty($title) && empty($url)) wp_send_json_error(['message' => 'العنوان أو الرابط مطلوب']);
        if (!FCM::is_ready()) wp_send_json_error(['message' => 'Firebase غير مهيأ']);
        
        $result = FCM::send($title ?: 'تنبيه', $body ?: '', $url, $target ?: 'all');
        wp_send_json_success(['sent' => $result['sent'], 'failed' => $result['failed']]);
    }

    // ============ Render Page ============

    public static function render() {
        $config  = Settings::get_all();
        $devices = Settings::get_devices();
        $fcm_ok  = FCM::is_ready();
        ?>
        <div class="tdl-wrap">
            <!-- Header -->
            <div class="tdl-header">
                <div>
                    <h1>📡 إدارة تطبيق TikTokDL</h1>
                    <p>لوحة تحكم مركزية للتحكم بجميع إعدادات التطبيق عن بُعد</p>
                </div>
                <div class="tdl-badges">
                    <span class="tdl-badge <?php echo $fcm_ok ? 'green' : 'red'; ?>"><?php echo $fcm_ok ? '✅ FCM' : '❌ FCM'; ?></span>
                    <span class="tdl-badge blue">📱 <?php echo count($devices); ?></span>
                    <span class="tdl-badge gray">v<?php echo TDL_VERSION; ?></span>
                </div>
            </div>

            <!-- Toast Notification -->
            <div id="tdl-toast" class="tdl-toast"></div>

            <!-- API Info -->
            <div class="tdl-api-info">
                <span>🔑 <code><?php echo substr(TDL_API_KEY, 0, 8) . str_repeat('•', 16) . substr(TDL_API_KEY, -4); ?></code></span>
                <span>📡 <code><?php echo rest_url('app/v1/config'); ?></code></span>
            </div>

            <!-- Tabs -->
            <div class="tdl-tabs">
                <button class="tdl-tab active" data-tab="tab-general">⚙️ إعدادات عامة</button>
                <button class="tdl-tab" data-tab="tab-scraping">🔍 خوارزميات التحميل</button>
                <button class="tdl-tab" data-tab="tab-features">🎛 الميزات والإعلانات</button>
                <button class="tdl-tab" data-tab="tab-notifications">🚀 الإشعارات</button>
            </div>

            <!-- Tab 1: General -->
            <form id="tdl-form" class="tdl-tab-content active" data-tab="tab-general">
                <div class="tdl-card">
                    <div class="tdl-card-title">🔄 الصيانة والتحديثات</div>
                    <div class="tdl-card-body">
                        <div class="tdl-field">
                            <label>وضع الصيانة</label>
                            <label class="tdl-switch"><input type="checkbox" name="maintenance_mode" <?php checked($config['maintenance_mode']); ?>><span></span></label>
                        </div>
                        <div class="tdl-field">
                            <label>رسالة الصيانة</label>
                            <input type="text" name="maintenance_message" value="<?php echo esc_attr($config['maintenance_message']); ?>" dir="rtl">
                        </div>
                        <hr>
                        <div class="tdl-field">
                            <label>رقم الإصدار الأخير</label>
                            <input type="number" name="app_version" value="<?php echo (int)$config['app_version']; ?>" style="width:100px">
                        </div>
                        <div class="tdl-field">
                            <label>تحديث إجباري</label>
                            <label class="tdl-switch"><input type="checkbox" name="force_update" <?php checked($config['force_update']); ?>><span></span></label>
                        </div>
                        <div class="tdl-field">
                            <label>رابط التحديث</label>
                            <input type="text" name="update_url" value="<?php echo esc_attr($config['update_url']); ?>" dir="ltr">
                        </div>
                        <div class="tdl-field">
                            <label>رسالة التحديث</label>
                            <input type="text" name="update_message" value="<?php echo esc_attr($config['update_message']); ?>" dir="rtl">
                        </div>
                    </div>
                </div>

                <div class="tdl-card">
                    <div class="tdl-card-title">👨‍💻 وضع المطورين</div>
                    <div class="tdl-card-body">
                        <div class="tdl-field">
                            <label>تفعيل وضع المطورين</label>
                            <label class="tdl-switch"><input type="checkbox" name="developer_mode" <?php checked($config['developer_mode']); ?>><span></span></label>
                        </div>
                        <div class="tdl-field" style="flex-direction:column;align-items:flex-start">
                            <label>معرفات الأجهزة المسموحة</label>
                            <textarea name="developer_ids" rows="3" dir="ltr" placeholder="device-id-1, device-id-2"><?php echo esc_textarea($config['developer_ids']); ?></textarea>
                            <span class="desc">Device UUIDs مفصولة بفواصل</span>
                        </div>
                    </div>
                </div>

                <button type="submit" class="tdl-btn primary">💾 حفظ الإعدادات العامة</button>
            </form>

            <!-- Tab 2: Scraping -->
            <form class="tdl-tab-content" data-tab="tab-scraping">
                <div class="tdl-card">
                    <div class="tdl-card-title">🔍 محددات الكشط (CSS Selectors & RegEx)</div>
                    <div class="tdl-card-body">
                        <p class="desc" style="margin-bottom:16px">⚠️ عند تغيير TikTok لتركيب الصفحة، عدّل القيم هنا بدون تحديث التطبيق.</p>
                        <div class="tdl-field"><label>محدد الفيديو</label><input type="text" name="selector_video" value="<?php echo esc_attr($config['selector_video']); ?>" dir="ltr"></div>
                        <div class="tdl-field"><label>محدد Open Graph</label><input type="text" name="selector_og" value="<?php echo esc_attr($config['selector_og']); ?>" dir="ltr"></div>
                        <div class="tdl-field"><label>محدد JSON-LD</label><input type="text" name="selector_jsonld" value="<?php echo esc_attr($config['selector_jsonld']); ?>" dir="ltr"></div>
                        <div class="tdl-field"><label>تعبير نمطي (RegEx)</label><input type="text" name="selector_regex" value="<?php echo esc_attr($config['selector_regex']); ?>" dir="ltr"></div>
                    </div>
                </div>

                <div class="tdl-card">
                    <div class="tdl-card-title">🔗 روابط السيرفر</div>
                    <div class="tdl-card-body">
                        <div class="tdl-field"><label>رابط API التحميل</label><input type="text" name="api_download_url" value="<?php echo esc_attr($config['api_download_url']); ?>" dir="ltr"></div>
                        <div class="tdl-field"><label>البريد الإلكتروني</label><input type="text" name="contact_email" value="<?php echo esc_attr($config['contact_email']); ?>" dir="ltr"></div>
                        <div class="tdl-field"><label>بوت تلجرام</label><input type="text" name="telegram_bot" value="<?php echo esc_attr($config['telegram_bot']); ?>" dir="ltr"></div>
                    </div>
                </div>

                <!-- Scraper Tester -->
                <div class="tdl-card">
                    <div class="tdl-card-title">🧪 اختبار الكشط (Live Test)</div>
                    <div class="tdl-card-body">
                        <div id="tdl-scrape-form">
                            <div class="tdl-field">
                                <input type="text" id="tdl-scrape-url" placeholder="https://vm.tiktok.com/ZMexample/" dir="ltr" style="flex:1">
                                <button type="button" id="tdl-scrape-btn" class="tdl-btn secondary" style="white-space:nowrap">🔍 فحص الرابط</button>
                            </div>
                            <div id="tdl-scrape-result" style="margin-top:12px;display:none"></div>
                        </div>
                    </div>
                </div>

                <button type="submit" class="tdl-btn primary">💾 حفظ إعدادات الكشط</button>
            </form>

            <!-- Tab 3: Features -->
            <form class="tdl-tab-content" data-tab="tab-features">
                <div class="tdl-card">
                    <div class="tdl-card-title">🎛 مفاتيح التحكم</div>
                    <div class="tdl-card-body">
                        <div class="tdl-grid">
                            <?php
                            $toggles = [
                                'download_enabled'      => ['تحميل الفيديو', 'السماح بتحميل الفيديوهات'],
                                'background_download'   => ['التحميل في الخلفية', 'استمرار التحميل عند إغلاق التطبيق'],
                                'hd_quality_enabled'    => ['جودة HD', 'خيارات الجودة المتعددة'],
                                'mp3_conversion'        => ['تحويل MP3', 'استخراج الصوت من الفيديو'],
                                'ads_enabled'           => ['الإعلانات (AdMob)', 'تشغيل الإعلانات'],
                                'auto_clipboard'        => ['اكتشاف الحافظة', 'التقاط روابط TikTok المنسوخة'],
                            ];
                            foreach ($toggles as $key => $info):
                            ?>
                            <div class="tdl-toggle-card">
                                <label class="tdl-switch">
                                    <input type="checkbox" name="<?php echo $key; ?>" <?php checked($config[$key]); ?>>
                                    <span></span>
                                </label>
                                <div>
                                    <strong><?php echo $info[0]; ?></strong>
                                    <p><?php echo $info[1]; ?></p>
                                </div>
                            </div>
                            <?php endforeach; ?>
                        </div>
                        <div class="tdl-field" style="margin-top:16px">
                            <label>الحد الأقصى اليومي:</label>
                            <input type="number" name="max_downloads_per_day" value="<?php echo (int)$config['max_downloads_per_day']; ?>" style="width:100px">
                            <span class="desc">0 = غير محدود</span>
                        </div>
                    </div>
                </div>

                <div class="tdl-card">
                    <div class="tdl-card-title">📢 إعدادات AdMob</div>
                    <div class="tdl-card-body">
                        <div class="tdl-field"><label>App ID</label><input type="text" name="admob_app_id" value="<?php echo esc_attr($config['admob_app_id']); ?>" dir="ltr"></div>
                        <div class="tdl-field"><label>Banner ID</label><input type="text" name="admob_banner_id" value="<?php echo esc_attr($config['admob_banner_id']); ?>" dir="ltr"></div>
                        <div class="tdl-field"><label>Interstitial ID</label><input type="text" name="admob_interstitial" value="<?php echo esc_attr($config['admob_interstitial']); ?>" dir="ltr"></div>
                    </div>
                </div>

                <button type="submit" class="tdl-btn primary">💾 حفظ الميزات</button>
            </form>

            <!-- Tab 4: Notifications -->
            <div class="tdl-tab-content" data-tab="tab-notifications">
                <div class="tdl-card">
                    <div class="tdl-card-title">🚀 إرسال إشعار فوري</div>
                    <div class="tdl-card-body">
                        <?php if (!$fcm_ok): ?>
                        <div class="tdl-toast error" style="position:static;display:block">⚠️ Firebase غير مهيأ. ضع service-account.json في مجلد الإضافة.</div>
                        <?php else: ?>
                        <div id="tdl-push-form">
                            <div class="tdl-field" style="flex-direction:column;align-items:flex-start">
                                <label>عنوان الإشعار</label>
                                <input type="text" id="tdl-push-title" placeholder="فيديو جديد جاهز!" dir="rtl">
                            </div>
                            <div class="tdl-field" style="flex-direction:column;align-items:flex-start">
                                <label>النص / الرابط</label>
                                <input type="text" id="tdl-push-body" placeholder="https://vm.tiktok.com/..." dir="ltr">
                            </div>
                            <div class="tdl-field" style="flex-direction:column;align-items:flex-start">
                                <label>الرابط المفتوح</label>
                                <input type="text" id="tdl-push-url" placeholder="https://vm.tiktok.com/..." dir="ltr">
                            </div>
                            <div class="tdl-field">
                                <label>إرسال إلى</label>
                                <select id="tdl-push-target">
                                    <option value="all">📢 جميع الأجهزة (<?php echo count($devices); ?>)</option>
                                    <?php foreach ($devices as $token => $d): ?>
                                    <option value="<?php echo esc_attr($token); ?>">📱 <?php echo esc_html($d['device'] . ' (..' . substr($token, -6) . ')'); ?></option>
                                    <?php endforeach; ?>
                                </select>
                            </div>
                            <button type="button" id="tdl-push-btn" class="tdl-btn danger">🚀 إرسال الآن</button>
                            <span id="tdl-push-spinner" class="tdl-spinner" style="display:none;margin-right:10px"></span>
                        </div>
                        <?php endif; ?>
                    </div>
                </div>

                <!-- Health Check -->
                <div class="tdl-card">
                    <div class="tdl-card-title">🩺 فحص صحة API</div>
                    <div class="tdl-card-body">
                        <button type="button" id="tdl-health-btn" class="tdl-btn secondary">🔄 اختبار الاتصال</button>
                        <span id="tdl-health-spinner" class="tdl-spinner" style="display:none;margin-right:10px"></span>
                        <div id="tdl-health-result" style="margin-top:12px;display:none"></div>
                    </div>
                </div>
            </div>

        </div>
        <?php
    }
}
