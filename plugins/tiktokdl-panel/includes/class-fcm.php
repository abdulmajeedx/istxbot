<?php
namespace TikTokDL;

class FCM {

    private static $sa_file;
    private static $project_id;

    public static function init() {
        self::$sa_file = TDL_DIR . 'service-account.json';

        // Handler for push notification form submission
        add_action('admin_post_tdl_send_push', [__CLASS__, 'handle_push']);
    }

    public static function is_ready() {
        if (!file_exists(self::$sa_file)) return false;
        if (!self::$project_id) {
            $sa = json_decode(file_get_contents(self::$sa_file), true);
            self::$project_id = $sa['project_id'] ?? '';
        }
        return !empty(self::$project_id);
    }

    // ============ Send Push Notification ============

    public static function handle_push() {
        if (!current_user_can('manage_options')) wp_die('غير مصرح');

        check_admin_referer('tdl_push_nonce');

        $title  = sanitize_text_field($_POST['push_title'] ?? '');
        $body   = sanitize_text_field($_POST['push_body'] ?? '');
        $url    = sanitize_text_field($_POST['push_url'] ?? '');
        $target = sanitize_text_field($_POST['push_target'] ?? 'all');

        if (empty($title) && empty($body)) {
            wp_redirect(add_query_arg(['tdl_msg' => 'error', 'tdl_txt' => 'العنوان أو النص مطلوب'], wp_get_referer()));
            exit;
        }

        if (!self::is_ready()) {
            wp_redirect(add_query_arg(['tdl_msg' => 'error', 'tdl_txt' => 'Firebase غير مهيأ'], wp_get_referer()));
            exit;
        }

        $result = self::send($title, $body, $url, $target);

        $txt = sprintf('تم الإرسال: %d نجاح, %d فشل', $result['sent'], $result['failed']);
        wp_redirect(add_query_arg(['tdl_msg' => 'success', 'tdl_txt' => urlencode($txt)], wp_get_referer()));
        exit;
    }

    public static function send($title, $body, $url, $target) {
        $devices = Settings::get_devices();
        $sent = 0; $failed = 0;

        foreach ($devices as $token => $info) {
            if ($target !== 'all' && $token !== $target) continue;
            if (self::send_one($token, $title, $body, $url)) $sent++;
            else $failed++;
        }

        return ['sent' => $sent, 'failed' => $failed];
    }

    /**
     * إرسال إشعار تحديث الإعدادات لكل الأجهزة (Config Update Event)
     */
    public static function send_config_update() {
        $devices = Settings::get_devices();
        $sent = 0;
        foreach ($devices as $token => $info) {
            if (self::send_data_only($token, 'config_update', ['sync' => '1'])) $sent++;
        }
        return ['sent' => $sent];
    }

    /**
     * إرسال Data Message صامت (بدون إشعار مرئي) - لتحديث الإعدادات بالخلفية
     */
    private static function send_data_only($token, $type, $data = []) {
        if (empty(self::$project_id)) return false;
        $access_token = self::get_access_token();
        if (!$access_token) return false;

        $message = [
            'message' => [
                'token' => $token,
                'data'  => array_merge(['type' => $type], $data),
                'android' => ['priority' => 'high', 'ttl' => '0s'],
            ],
        ];

        $ch = curl_init("https://fcm.googleapis.com/v1/projects/" . self::$project_id . "/messages:send");
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_HTTPHEADER => ['Authorization: Bearer '.$access_token, 'Content-Type: application/json'],
            CURLOPT_POSTFIELDS => json_encode($message),
            CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 10
        ]);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        return $http_code >= 200 && $http_code < 300;
    }

    private static function send_one($token, $title, $body, $url) {
        if (empty(self::$project_id)) return false;

        $access_token = self::get_access_token();
        if (!$access_token) return false;

        $message = [
            'message' => [
                'token' => $token,
                'data'  => [
                    'url'   => $url,
                    'title' => $title,
                    'body'  => $body,
                ],
                'android' => ['priority' => 'high'],
            ],
        ];

        // Also include notification for when app is in background
        if ($title) {
            $message['message']['notification'] = [
                'title' => $title,
                'body'  => $body ?: $url,
            ];
        }

        $ch = curl_init("https://fcm.googleapis.com/v1/projects/" . self::$project_id . "/messages:send");
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_HTTPHEADER     => [
                'Authorization: Bearer ' . $access_token,
                'Content-Type: application/json',
            ],
            CURLOPT_POSTFIELDS     => json_encode($message),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 10,
        ]);

        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        return $http_code >= 200 && $http_code < 300;
    }

    // ============ OAuth2 Access Token ============

    private static function get_access_token() {
        if (!file_exists(self::$sa_file)) return null;

        $sa = json_decode(file_get_contents(self::$sa_file), true);
        if (!$sa || empty($sa['private_key'])) return null;

        // JWT Header
        $header = self::base64url(json_encode(['alg' => 'RS256', 'typ' => 'JWT']));

        // JWT Payload
        $now = time();
        $payload = self::base64url(json_encode([
            'iss'   => $sa['client_email'],
            'scope' => 'https://www.googleapis.com/auth/firebase.messaging',
            'aud'   => $sa['token_uri'],
            'exp'   => $now + 3600,
            'iat'   => $now,
        ]));

        // Sign
        $signature = '';
        openssl_sign("$header.$payload", $signature, $sa['private_key'], 'SHA256');
        $jwt = "$header.$payload." . self::base64url($signature);

        // Exchange for access token
        $ch = curl_init($sa['token_uri']);
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => http_build_query([
                'grant_type' => 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                'assertion'  => $jwt,
            ]),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 10,
        ]);

        $response = json_decode(curl_exec($ch), true);
        curl_close($ch);

        return $response['access_token'] ?? null;
    }

    private static function base64url($data) {
        return rtrim(strtr(base64_encode($data), '+/', '-_'), '=');
    }
}
