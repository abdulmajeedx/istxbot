<?php
namespace TikTokDL;

class API {

    public static function init() {
        add_action('rest_api_init', [__CLASS__, 'register_routes']);
        add_action('init', [__CLASS__, 'handle_legacy']);
    }

    // ============ REST API Routes ============

    public static function register_routes() {

        // GET /wp-json/app/v1/config - إعدادات التطبيق
        register_rest_route('app/v1', '/config', [
            'methods'             => 'GET',
            'callback'            => [__CLASS__, 'get_config'],
            'permission_callback' => [__CLASS__, 'authenticate'],
        ]);

        // POST /wp-json/app/v1/notify - إرسال إشعار
        register_rest_route('app/v1', '/notify', [
            'methods'             => 'POST',
            'callback'            => [__CLASS__, 'send_notification'],
            'permission_callback' => [__CLASS__, 'authenticate'],
        ]);

        // POST /wp-json/app/v1/register - تسجيل جهاز
        register_rest_route('app/v1', '/register', [
            'methods'             => 'POST',
            'callback'            => [__CLASS__, 'register_device'],
            'permission_callback' => '__return_true', // مفتوح للتسجيل
        ]);

        // POST /wp-json/app/v1/poll - استطلاع الأوامر (للخدمة الخلفية)
        register_rest_route('app/v1', '/poll', [
            'methods'             => 'GET',
            'callback'            => [__CLASS__, 'poll_commands'],
            'permission_callback' => '__return_true',
        ]);

        // GET /wp-json/app/v1/health - فحص صحة API (لاختبار الاتصال)
        register_rest_route('app/v1', '/health', [
            'methods'             => 'GET',
            'callback'            => [__CLASS__, 'health_check'],
            'permission_callback' => '__return_true',
        ]);

        // POST /wp-json/app/v1/scraper-test - اختبار الكشط
        register_rest_route('app/v1', '/scraper-test', [
            'methods'             => 'POST',
            'callback'            => [__CLASS__, 'scraper_test'],
            'permission_callback' => [__CLASS__, 'authenticate'],
        ]);
    }

    // ============ Authentication ============

    public static function authenticate() {
        // رفض api_key من الرابط (يسجل في سجلات nginx)
        if (isset($_GET['api_key'])) {
            return false;
        }
        $key = $_SERVER['HTTP_X_API_KEY'] ?? '';
        return hash_equals(TDL_API_KEY, $key);
    }

    // ============ Callbacks ============

    /**
     * GET /app/v1/config
     * يرجع JSON كامل بكل إعدادات التطبيق
     */
    public static function get_config() {
        // Transient cache (5 min) + file fallback
        $cache_key = 'tdl_api_config';
        $cached = get_transient($cache_key);

        // Fallback: file-based cache
        if ($cached === false) {
            $cache_file = TDL_DIR . 'data/config-cache.json';
            if (file_exists($cache_file) && (time() - filemtime($cache_file)) < 300) {
                $cached = json_decode(file_get_contents($cache_file), true);
            }
        }

        if ($cached !== false && is_array($cached) && isset($cached['config'])) {
            $cached['from_cache'] = true;
            return rest_ensure_response($cached);
        }

        $config = Settings::get_all();
        $config['server_time']     = current_time('mysql');
        $config['fcm_project_id']  = FCM::is_ready() ? self::get_project_id() : '';
        $config['api_version']     = TDL_VERSION;
        $config['registered_devices'] = count(Settings::get_devices());
        $config['developer_mode']  = Settings::is_developer_mode();
        $config['developer_ids']   = Settings::get_developer_device_ids();
        $config['api_health_url']  = rest_url('app/v1/health');
        $config['from_cache']      = false;

        $response = [
            'success'    => true,
            'config'     => $config,
            'updated_at' => current_time('mysql'),
        ];

        // Store in both transient and file cache
        set_transient($cache_key, $response, 300);
        $cache_file = TDL_DIR . 'data/config-cache.json';
        file_put_contents($cache_file, json_encode($response));

        return rest_ensure_response($response);
    }

    /**
     * POST /app/v1/notify
     * يستقبل {title, body, url, target} ويرسل إشعار FCM
     */
    public static function send_notification($request) {
        $title  = sanitize_text_field($request->get_param('title'));
        $body   = sanitize_text_field($request->get_param('body'));
        $url    = sanitize_text_field($request->get_param('url'));
        $target = sanitize_text_field($request->get_param('target'));

        if (empty($title) && empty($url)) {
            return rest_ensure_response(['success' => false, 'error' => 'title or url required'], 400);
        }

        if (!FCM::is_ready()) {
            return rest_ensure_response(['success' => false, 'error' => 'FCM not configured'], 500);
        }

        $result = FCM::send($title ?: 'تنبيه', $body ?: '', $url, $target ?: 'all');

        return rest_ensure_response([
            'success' => true,
            'sent'    => $result['sent'],
            'failed'  => $result['failed'],
        ]);
    }

    /**
     * POST /app/v1/register
     * يسجل جهاز جديد مع FCM Token
     */
    public static function register_device($request) {
        $token  = sanitize_text_field($request->get_param('token'));
        $device = sanitize_text_field($request->get_param('device'));

        if (empty($token)) {
            return rest_ensure_response(['success' => false, 'error' => 'token required'], 400);
        }

        Settings::save_device($token, $device ?: 'جهاز غير معروف');

        // أيضاً أضف أمر انتظار إذا وجد
        $pending_url = $request->get_param('pending_url');
        if ($pending_url) {
            Settings::add_command($pending_url);
        }

        return rest_ensure_response(['success' => true, 'device' => $device]);
    }

    /**
     * GET /app/v1/poll
     * استطلاع الأوامر المعلقة للخدمة الخلفية
     */
    public static function poll_commands() {
        $pass = $_GET['pass'] ?? '';
        if ($pass !== 'admin123') {
            return rest_ensure_response(['success' => false, 'error' => 'كلمة المرور غير صحيحة'], 403);
        }

        $commands = Settings::get_commands();
        $pending  = [];

        foreach ($commands as $id => $cmd) {
            if ($cmd['status'] === 'pending') {
                $pending[] = array_merge(['id' => $id], $cmd);
            }
        }

        return rest_ensure_response([
            'success'  => true,
            'commands' => $pending,
            'count'    => count($pending),
        ]);
    }

    // ============ Legacy Support ============

    /**
     * دعم API القديم (?tdl_api=poll, ?tdl_api=register_device)
     */
    public static function handle_legacy() {
        if (!isset($_GET['tdl_api'])) return;

        $api = $_GET['tdl_api'];

        if ($api === 'register_device') {
            $token  = $_GET['token'] ?? '';
            $device = $_GET['device'] ?? 'Unknown';
            if ($token) Settings::save_device($token, $device);
            wp_send_json(['success' => true]);
        }

        if ($api === 'poll') {
            if (($_GET['pass'] ?? '') !== 'admin123') {
                wp_send_json(['success' => false]);
            }
            $cmds = Settings::get_commands();
            $res = [];
            foreach ($cmds as $id => $c) {
                if ($c['status'] === 'pending') $res[] = array_merge(['id' => $id], $c);
            }
            wp_send_json(['success' => true, 'commands' => $res]);
        }
    }

    /**
     * GET /app/v1/health - فحص صحة API وكل الخدمات
     */
    public static function health_check() {
        $checks = [];

        // Check 1: WordPress core
        $checks['wordpress'] = ['status' => 'ok', 'version' => get_bloginfo('version')];

        // Check 2: Plugin active
        $checks['plugin'] = ['status' => 'ok', 'version' => TDL_VERSION];

        // Check 3: FCM available
        $checks['fcm'] = ['status' => FCM::is_ready() ? 'ok' : 'error'];

        // Check 4: Devices file writable
        $data_dir = TDL_DIR . 'data';
        $checks['storage'] = ['status' => is_writable($data_dir) ? 'ok' : 'error'];

        // Check 5: API download endpoint
        $api_url = Settings::get('api_download_url');
        $checks['download_api'] = ['status' => 'unknown', 'url' => $api_url];

        // Overall status
        $all_ok = true;
        foreach ($checks as $c) {
            if (($c['status'] ?? '') === 'error') $all_ok = false;
        }

        return rest_ensure_response([
            'success'    => $all_ok,
            'checked_at' => current_time('mysql'),
            'checks'     => $checks,
            'config'     => [
                'app_version'    => Settings::get('app_version'),
                'developer_mode' => Settings::is_developer_mode(),
                'devices_count'  => count(Settings::get_devices()),
                'maintenance'    => Settings::get('maintenance_mode'),
            ],
        ]);
    }

    /**
     * POST /app/v1/scraper-test - اختبار كشط رابط (للأدمن فقط)
     */
    public static function scraper_test($request) {
        if (!self::authenticate()) {
            return rest_ensure_response(['success' => false, 'error' => 'Unauthorized'], 401);
        }

        $url = sanitize_text_field($request->get_param('url'));
        if (empty($url)) {
            return rest_ensure_response(['success' => false, 'error' => 'URL required'], 400);
        }

        $result = \TikTokDL\ScraperValidator::validate($url);
        return rest_ensure_response($result);
    }

    private static function get_project_id() {
        $sa_file = TDL_DIR . 'service-account.json';
        if (!file_exists($sa_file)) return '';
        $sa = json_decode(file_get_contents($sa_file), true);
        return $sa['project_id'] ?? '';
    }
}
