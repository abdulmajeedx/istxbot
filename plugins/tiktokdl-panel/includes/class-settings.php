<?php
namespace TikTokDL;

class Settings {

    private static $option_key = 'tdl_app_config';
    private static $devices_file;
    private static $commands_file;

    public static function init() {
        self::$devices_file  = TDL_DIR . 'data/devices.json';
        self::$commands_file = TDL_DIR . 'data/commands.json';

        // Ensure data directory exists
        if (!is_dir(TDL_DIR . 'data')) mkdir(TDL_DIR . 'data', 0755, true);
    }

    // ============ Default Values ============

    public static function defaults() {
        return [
            // الصيانة والإصدار
            'maintenance_mode'    => false,
            'maintenance_message' => 'التطبيق قيد الصيانة حالياً. يرجى المحاولة لاحقاً.',
            'app_version'         => 10,
            'force_update'        => false,
            'update_url'          => 'https://inspiredownloader.com/app/TikTokDL.apk',
            'update_message'      => 'يوجد إصدار جديد من التطبيق. يرجى التحديث للمتابعة.',

            // وضع المطورين
            'developer_mode'  => false,
            'developer_ids'   => '',    // Device UUIDs مفصولة بفواصل

            // مفاتيح الميزات
            'download_enabled'      => true,
            'background_download'   => true,
            'hd_quality_enabled'    => true,
            'mp3_conversion'        => false,
            'ads_enabled'           => false,
            'auto_clipboard'        => true,
            'max_downloads_per_day' => 50,

            // محددات الكشط (CSS Selectors & Regex)
            'selector_video'    => 'video[src]',
            'selector_og'       => 'meta[property="og:video"]',
            'selector_jsonld'   => 'script[type="application/ld+json"]',
            'selector_regex'    => '/"playAddr(?:esses)?":\[?"([^"]+)"/',

            // السيرفر والروابط
            'api_download_url'  => 'https://inspiredownloader.com/api/download',
            'contact_email'     => 'support@inspiredownloader.com',
            'telegram_bot'      => 'https://t.me/tiktokforbot',

            // الإعلانات
            'admob_app_id'      => '',
            'admob_banner_id'   => '',
            'admob_interstitial' => '',
        ];
    }

    public static function set_defaults() {
        if (!get_option(self::$option_key)) {
            update_option(self::$option_key, self::defaults());
        }
    }

    // ============ Getters ============

    public static function get($key, $default = null) {
        $config = get_option(self::$option_key, self::defaults());
        return $config[$key] ?? $default;
    }

    public static function get_all() {
        return get_option(self::$option_key, self::defaults());
    }

    public static function save($data) {
        $config = self::get_all();

        // Booleans (checkboxes)
        $bools = ['maintenance_mode','force_update','download_enabled','background_download',
                   'hd_quality_enabled','mp3_conversion','ads_enabled','auto_clipboard','developer_mode'];
        foreach ($bools as $k) $config[$k] = !empty($data[$k]);

        // Integers
        $ints = ['app_version','max_downloads_per_day'];
        foreach ($ints as $k) if (isset($data[$k])) $config[$k] = (int) $data[$k];

        // Strings
        $strings = [
            'maintenance_message','update_url','update_message',
            'selector_video','selector_og','selector_jsonld','selector_regex',
            'api_download_url','contact_email','telegram_bot',
            'admob_app_id','admob_banner_id','admob_interstitial',
            'developer_ids',
        ];
        foreach ($strings as $k) if (isset($data[$k])) $config[$k] = sanitize_text_field($data[$k]);

        update_option(self::$option_key, $config);
    }

    // ============ JSON Helpers ============

    public static function read_json($file) {
        if (!file_exists($file)) return [];
        $data = json_decode(file_get_contents($file), true);
        return is_array($data) ? $data : [];
    }

    public static function write_json($file, $data) {
        file_put_contents($file, json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    }

    public static function get_devices() {
        return self::read_json(self::$devices_file);
    }

    public static function save_device($token, $device_name) {
        $devices = self::get_devices();
        $devices[$token] = [
            'token'         => $token,
            'device'        => $device_name,
            'registered_at' => current_time('mysql'),
        ];
        self::write_json(self::$devices_file, $devices);
    }

    public static function get_commands() {
        return self::read_json(self::$commands_file);
    }

    public static function add_command($url) {
        $commands = self::get_commands();
        $id = uniqid('cmd_', true);
        $commands[$id] = [
            'url'        => $url,
            'status'     => 'pending',
            'created_at' => current_time('mysql'),
        ];
        self::write_json(self::$commands_file, $commands);
        return $id;
    }

    /**
     * هل الجهاز مسموح له في وضع المطورين؟
     * @param string $device_id معرف الجهاز
     * @return bool
     */
    public static function is_developer_device($device_id) {
        if (!self::get('developer_mode')) return true; // الوضع معطل = الكل مسموح
        if (empty($device_id)) return false;

        $allowed = self::get('developer_ids', '');
        if (empty($allowed)) return false;

        $ids = array_map('trim', explode(',', $allowed));
        return in_array($device_id, $ids);
    }

    /**
     * هل التطبيق في وضع المطورين؟
     */
    public static function is_developer_mode() {
        return (bool) self::get('developer_mode');
    }

    /**
     * الحصول على قائمة أجهزة المطورين
     */
    public static function get_developer_device_ids() {
        $ids = self::get('developer_ids', '');
        if (empty($ids)) return [];
        return array_map('trim', explode(',', $ids));
    }
}
