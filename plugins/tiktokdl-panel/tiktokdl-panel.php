<?php
/**
 * Plugin Name:  إدارة تطبيق TikTokDL
 * Plugin URI:   https://inspiredownloader.com
 * Description:  لوحة تحكم عربية متكاملة للتحكم بتطبيق TikTokDL عن بُعد. REST API آمن، تحكم بالإصدارات، إشعارات فورية، ومحددات كشط ديناميكية.
 * Version:      3.0.0
 * Author:       TikTokDL Team
 * Text Domain:  tiktokdl-panel
 * Domain Path:  /languages
 */

defined('ABSPATH') || exit;

define('TDL_VERSION', '3.0.0');
define('TDL_DIR', plugin_dir_path(__FILE__));
define('TDL_URL', plugin_dir_url(__FILE__));
define('TDL_API_KEY', 'tdl_sk_2026_secure_key_x7k9'); // غيّره لاحقاً

// Autoload classes
spl_autoload_register(function ($class) {
    $prefix = 'TikTokDL\\';
    if (strpos($class, $prefix) !== 0) return;
    $file = TDL_DIR . 'includes/class-' . strtolower(str_replace($prefix, '', $class)) . '.php';
    if (file_exists($file)) require_once $file;
});

// Initialize
add_action('plugins_loaded', function () {
    TikTokDL\Settings::init();
    TikTokDL\Admin::init();
    TikTokDL\API::init();
    TikTokDL\FCM::init();
});

// Activation
register_activation_hook(__FILE__, function () {
    TikTokDL\Settings::set_defaults();
    flush_rewrite_rules();
});

register_deactivation_hook(__FILE__, function () {
    flush_rewrite_rules();
});
