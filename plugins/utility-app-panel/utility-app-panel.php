<?php
/**
 * Plugin Name:       مدير تطبيق الخدمات الشخصية
 * Plugin URI:        https://inspiredownloader.com
 * Description:       قائمة جانبية معزولة في أدمن ووردبريس — 3 تبويبات (إعدادات، إعلانات، تشخيص) مع حفظ AJAX و Toggle Switches عصرية.
 * Version:           3.0.0
 * Author:            Inspiredownloader
 * Author URI:        https://inspiredownloader.com
 * Text Domain:       utility-app
 * Requires PHP:      7.4
 * Requires at least: 5.8
 *
 * للاستخدام داخل functions.php: احذف التعليق العلوي (Plugin Header) وألصق الكود من السطر 28 وما بعده.
 *
 * @package UtilityAppAdmin
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

/* ================================================================
 * 1. الثوابت — Prefix معزول `utility_app_`
 * ================================================================ */
define( 'UAPP_SLUG',        'utility-app-panel' );
define( 'UAPP_OPTION_KEY',  'utility_app_settings' );
define( 'UAPP_CAP',         'manage_options' );
define( 'UAPP_NONCE_ACTION', 'utility_app_nonce' );
define( 'UAPP_AJAX_GENERAL', 'uapp_save_general' );
define( 'UAPP_AJAX_ADS',     'uapp_save_ads' );
define( 'UAPP_AJAX_DIAG',    'uapp_run_diagnosis' );

/* ================================================================
 * 2. القيم الافتراضية
 * ================================================================ */
function uapp_defaults(): array
{
    return [
        'maintenance_mode'   => false,
        'maintenance_title'  => 'الصيانة جارية',
        'maintenance_msg'    => 'نعمل على تطوير التطبيق. يرجى المحاولة لاحقًا.',
        'app_version'        => '1.0.0',
        'force_update_url'   => 'https://play.google.com/store/apps/details?id=com.utilityapp',
        'admob_banner'       => true,
        'admob_interstitial' => true,
        'admob_rewarded'     => true,
        'updated_at'         => time(),
    ];
}

function uapp_get_settings(): array
{
    return wp_parse_args( get_option( UAPP_OPTION_KEY, [] ), uapp_defaults() );
}

/* ================================================================
 * 3. تسجيل القائمة الجانبية
 * ================================================================ */
function uapp_register_menu(): void
{
    add_menu_page(
        'تطبيق الخدمات الشخصية',
        'تطبيق الخدمات الشخصية',
        UAPP_CAP,
        UAPP_SLUG,
        'uapp_render_page',
        'dashicons-smartphone',
        3
    );
}
add_action( 'admin_menu', 'uapp_register_menu' );

/* ================================================================
 * 4. واجهة الصفحة — 3 تبويبات مدمجة
 * ================================================================ */
function uapp_render_page(): void
{
    if ( ! current_user_can( UAPP_CAP ) ) {
        wp_die( '🚫 لا تملك صلاحية الوصول.' );
    }

    $s = uapp_get_settings();
    ?>
    <div class="wrap uapp-wrap" dir="rtl">
        <h1 style="font-size:1.4em;margin-bottom:2px;">
            <span class="dashicons dashicons-smartphone" style="color:#1e73be;font-size:24px;width:24px;height:24px;vertical-align:middle;"></span>
            تطبيق الخدمات الشخصية
        </h1>
        <p style="color:#646970;font-size:13px;margin:0 0 18px 0;">تحكم في إعدادات تطبيق الأندرويد مباشرة من لوحة التحكم.</p>

        <!-- أزرار التبويبات -->
        <div class="uapp-tabs" role="tablist">
            <button type="button" class="uapp-tab active" data-tab="tab-general">⚙️ إعدادات النظام</button>
            <button type="button" class="uapp-tab" data-tab="tab-ads">💰 تحكم إعلانات AdMob</button>
            <button type="button" class="uapp-tab" data-tab="tab-events">📅 الأحداث</button>
            <button type="button" class="uapp-tab" data-tab="tab-diag">🩺 التشخيص</button>
        </div>

        <!-- ================================================================ -->
        <!-- التبويب 1: إعدادات النظام -->
        <!-- ================================================================ -->
        <div id="tab-general" class="uapp-panel active">
            <form class="uapp-form" data-action="<?php echo UAPP_AJAX_GENERAL; ?>">
                <div class="uapp-card">
                    <div class="uapp-card-title">🔧 وضع الصيانة</div>
                    <div class="uapp-row">
                        <div>
                            <strong>تفعيل وضع الصيانة</strong>
                            <small>يُظهر رسالة للمستخدمين عند التفعيل.</small>
                        </div>
                        <label class="uapp-toggle">
                            <input type="checkbox" name="maintenance_mode" value="1" <?php checked( $s['maintenance_mode'] ); ?>>
                            <span class="uapp-toggle-track"></span>
                        </label>
                    </div>
                    <div class="uapp-row">
                        <label>عنوان رسالة الصيانة</label>
                        <input type="text" name="maintenance_title" value="<?php echo esc_attr( $s['maintenance_title'] ); ?>" class="uapp-input" dir="rtl">
                    </div>
                    <div class="uapp-row">
                        <label>نص رسالة الصيانة</label>
                        <textarea name="maintenance_msg" class="uapp-input" dir="rtl" rows="2"><?php echo esc_textarea( $s['maintenance_msg'] ); ?></textarea>
                    </div>
                </div>

                <div class="uapp-card">
                    <div class="uapp-card-title">📱 الإصدار والتحديثات</div>
                    <div class="uapp-row">
                        <label>رقم الإصدار الحالي</label>
                        <input type="text" name="app_version" value="<?php echo esc_attr( $s['app_version'] ); ?>" class="uapp-input" dir="ltr" style="width:140px;">
                    </div>
                    <div class="uapp-row">
                        <label>رابط التحديث الإجباري</label>
                        <input type="url" name="force_update_url" value="<?php echo esc_url( $s['force_update_url'] ); ?>" class="uapp-input" dir="ltr" placeholder="https://play.google.com/store/apps/...">
                    </div>
                </div>

                <p style="margin-top:12px;">
                    <button type="submit" class="button button-primary button-large">💾 حفظ الإعدادات</button>
                    <span class="spinner uapp-spinner"></span>
                </p>
            </form>
        </div>

        <!-- ================================================================ -->
        <!-- التبويب 2: تحكم إعلانات AdMob -->
        <!-- ================================================================ -->
        <div id="tab-ads" class="uapp-panel">
            <form class="uapp-form" data-action="<?php echo UAPP_AJAX_ADS; ?>">
                <div class="uapp-card">
                    <div class="uapp-card-title">📢 وحدات إعلانات AdMob</div>
                    <div class="uapp-row">
                        <div>
                            <strong>إعلان البانر (Banner)</strong>
                            <small>شريط إعلاني أعلى/أسفل الشاشة.</small>
                        </div>
                        <label class="uapp-toggle">
                            <input type="checkbox" name="admob_banner" value="1" <?php checked( $s['admob_banner'] ); ?>>
                            <span class="uapp-toggle-track"></span>
                        </label>
                    </div>
                    <div class="uapp-row">
                        <div>
                            <strong>إعلان بيني (Interstitial)</strong>
                            <small>إعلان كامل بين الانتقالات.</small>
                        </div>
                        <label class="uapp-toggle">
                            <input type="checkbox" name="admob_interstitial" value="1" <?php checked( $s['admob_interstitial'] ); ?>>
                            <span class="uapp-toggle-track"></span>
                        </label>
                    </div>
                    <div class="uapp-row">
                        <div>
                            <strong>إعلان المكافآت (Rewarded)</strong>
                            <small>مكافأة للمستخدم مقابل المشاهدة.</small>
                        </div>
                        <label class="uapp-toggle">
                            <input type="checkbox" name="admob_rewarded" value="1" <?php checked( $s['admob_rewarded'] ); ?>>
                            <span class="uapp-toggle-track"></span>
                        </label>
                    </div>
                </div>
                <p style="margin-top:12px;">
                    <button type="submit" class="button button-primary button-large">💾 حفظ إعدادات الإعلانات</button>
                    <span class="spinner uapp-spinner"></span>
                </p>
            </form>
        </div>

        <!-- ================================================================ -->
        <!-- التبويب 3: الأحداث -->
        <div id="tab-events" class="uapp-panel">
            <?php uapp_render_events_tab(); ?>
        </div>

        <!-- التبويب 4: التشخيص -->
        <!-- ================================================================ -->
        <div id="tab-diag" class="uapp-panel">
            <div class="uapp-card">
                <div class="uapp-card-title">🩺 فحص سلامة النظام</div>
                <p style="color:#646970;margin-bottom:14px;">اضغط الزر لبدء فحص السيرفر والـ Endpoint والتأكد من جاهزية كل شيء.</p>
                <button type="button" id="uapp-diag-btn" class="button button-secondary button-large">🔍 بدء الفحص التشخيصي</button>
                <span id="uapp-diag-spinner" class="spinner" style="float:none;margin-top:0;"></span>
                <div id="uapp-diag-results" style="display:none;margin-top:20px;">
                    <table class="widefat striped" style="max-width:700px;">
                        <thead>
                            <tr><th style="width:40px;"></th><th>الفحص</th><th style="width:100px;">الحالة</th><th>التفاصيل</th></tr>
                        </thead>
                        <tbody id="uapp-diag-tbody"></tbody>
                    </table>
                    <div id="uapp-diag-summary" style="margin-top:12px;padding:12px 16px;border-radius:6px;font-weight:700;" hidden></div>
                </div>
            </div>
        </div>
    </div>

    <!-- ================================================================ -->
    <!-- CSS مضمّن -->
    <!-- ================================================================ -->
    <style>
        .uapp-wrap { max-width:750px; }
        .uapp-tabs { display:flex; gap:0; border-bottom:2px solid #c3c4c7; margin-bottom:22px; }
        .uapp-tab {
            background:#f0f0f1; border:1px solid #c3c4c7; border-bottom:none; padding:10px 18px;
            font-size:13px; font-weight:600; cursor:pointer; color:#3c434a; border-radius:6px 6px 0 0;
            margin-right:3px; position:relative; bottom:-2px; transition:background .15s;
        }
        .uapp-tab:hover { background:#e5e5e5; }
        .uapp-tab.active { background:#fff; color:#1e73be; border-bottom-color:#fff; }
        .uapp-panel { display:none; }
        .uapp-panel.active { display:block; }
        .uapp-card {
            background:#fff; border:1px solid #dcdcde; border-radius:8px; margin-bottom:16px;
            padding:18px 20px; box-shadow:0 1px 3px rgba(0,0,0,.04);
        }
        .uapp-card-title { font-size:1em; font-weight:700; border-bottom:1px solid #eee; padding-bottom:10px; margin-bottom:8px; }
        .uapp-row {
            display:flex; align-items:center; justify-content:space-between; padding:10px 0;
            border-bottom:1px solid #f0f0f1; gap:12px;
        }
        .uapp-row:last-child { border-bottom:none; }
        .uapp-row label { font-weight:600; font-size:13px; }
        .uapp-row small { color:#757575; font-size:11px; display:block; margin-top:2px; }
        .uapp-input { width:100%; max-width:360px; border:1px solid #8c8f94; border-radius:4px; padding:7px 10px; font-size:13px; }
        .uapp-input:focus { border-color:#1e73be; box-shadow:0 0 0 1px #1e73be; outline:none; }
        textarea.uapp-input { resize:vertical; min-height:56px; }

        /* Toggle Switch */
        .uapp-toggle { position:relative; display:inline-block; width:46px; height:24px; flex-shrink:0; }
        .uapp-toggle input { opacity:0; width:0; height:0; position:absolute; }
        .uapp-toggle-track {
            position:absolute; cursor:pointer; top:0;left:0;right:0;bottom:0;
            background:#c3c4c7; border-radius:24px; transition:.25s;
        }
        .uapp-toggle-track::before {
            content:""; position:absolute; height:18px; width:18px; left:3px; bottom:3px;
            background:#fff; border-radius:50%; transition:.25s; box-shadow:0 1px 3px rgba(0,0,0,.15);
        }
        .uapp-toggle input:checked + .uapp-toggle-track { background:#1e73be; }
        .uapp-toggle input:checked + .uapp-toggle-track::before { transform:translateX(22px); }
        .uapp-toggle input:focus + .uapp-toggle-track { box-shadow:0 0 0 2px rgba(30,115,190,.3); }

        /* Toast */
        .uapp-toast {
            position:fixed; top:32px; right:20px; z-index:99999; padding:11px 22px; border-radius:6px;
            color:#fff; font-weight:600; font-size:13px; opacity:0; transform:translateY(-20px);
            transition:all .3s; pointer-events:none; box-shadow:0 4px 14px rgba(0,0,0,.15);
        }
        .uapp-toast.show { opacity:1; transform:translateY(0); }
        .uapp-toast.ok { background:#00a32a; }
        .uapp-toast.err { background:#d63638; }

        /* Diagnosis colors */
        .uapp-diag-ok { color:#00a32a; font-weight:700; }
        .uapp-diag-fail { color:#d63638; font-weight:700; }
        .uapp-spinner { float:none !important; margin:0 0 0 8px !important; }
    </style>

    <!-- ================================================================ -->
    <!-- JavaScript مضمّن -->
    <!-- ================================================================ -->
    <script>
    jQuery(function($) {

        var ajaxUrl = '<?php echo admin_url( 'admin-ajax.php' ); ?>';
        var nonce   = '<?php echo wp_create_nonce( UAPP_NONCE_ACTION ); ?>';

        // ============================
        // التبويبات
        // ============================
        $('.uapp-tab').on('click', function() {
            var id = $(this).data('tab');
            $('.uapp-tab').removeClass('active');
            $(this).addClass('active');
            $('.uapp-panel').removeClass('active');
            $('#' + id).addClass('active');
        });

        // ============================
        // Toast
        // ============================
        function toast(msg, type) {
            var $t = $('#uapp-toast');
            if (!$t.length) { $t = $('<div id="uapp-toast" class="uapp-toast"></div>'); $('body').append($t); }
            $t.removeClass('ok err show').addClass(type + ' show').text(msg);
            clearTimeout($t.data('_tmr'));
            $t.data('_tmr', setTimeout(function(){ $t.removeClass('show'); }, 3000));
        }

        // ============================
        // حفظ النماذج عبر AJAX
        // ============================
        $('.uapp-form').on('submit', function(e) {
            e.preventDefault();
            var $form = $(this);
            var $btn  = $form.find('button[type=submit]');
            var $spin = $form.find('.spinner');
            var action = $form.data('action');
            var orig   = $btn.text();
            var data   = { action: action, nonce: nonce };

            $.each($form.serializeArray(), function(_, f) { data[f.name] = f.value; });

            $btn.prop('disabled', true).text('⏳ جارٍ الحفظ...');
            $spin.addClass('is-active');

            $.post(ajaxUrl, data)
                .done(function(res) {
                    toast(res && res.success ? '✅ تم الحفظ بنجاح' : ((res && res.data && res.data.msg) || '❌ فشل'), res && res.success ? 'ok' : 'err');
                })
                .fail(function() { toast('❌ خطأ في الاتصال', 'err'); })
                .always(function() { $btn.prop('disabled', false).text(orig); $spin.removeClass('is-active'); });
        });

        // ============================
        // التشخيص المباشر
        // ============================
        $('#uapp-diag-btn').on('click', function() {
            var $btn = $(this), $spin = $('#uapp-diag-spinner'), $res = $('#uapp-diag-results'), $tbody = $('#uapp-diag-tbody'), $sum = $('#uapp-diag-summary');
            $btn.prop('disabled', true).text('⏳ جارٍ الفحص...'); $spin.addClass('is-active');
            $tbody.empty(); $res.show(); $sum.hide();

            $.post(ajaxUrl, { action: '<?php echo UAPP_AJAX_DIAG; ?>', nonce: nonce })
                .done(function(response) {
                    if (!response || !response.success || !response.data || !response.data.results) {
                        $tbody.html('<tr><td colspan="4" style="color:#d63638;">تعذر إكمال التشخيص.</td></tr>'); return;
                    }
                    var icons = ['🖥️','🗄️','📡','🌐','💾','📁'], html = '', allOk = true;
                    $.each(response.data.results, function(i, r) {
                        allOk = allOk && r.status;
                        html += '<tr><td style="font-size:18px;text-align:center;">' + (icons[i] || '•') + '</td>' +
                                '<td>' + r.label + '</td>' +
                                '<td class="' + (r.status ? 'uapp-diag-ok' : 'uapp-diag-fail') + '">' + (r.status ? '✅ سليم' : '❌ خطأ') + '</td>' +
                                '<td style="font-size:13px;color:#50575e;">' + r.detail + '</td></tr>';
                    });
                    $tbody.html(html);
                    $sum.attr('hidden', false).text(allOk ? '🎉 جميع الفحوصات سليمة — النظام جاهز.' : '⚠️ توجد مشاكل — راجع التفاصيل أعلاه.')
                        .css({background: allOk ? '#edfaef' : '#fcf0f1', color: allOk ? '#007017' : '#b32d2e', border: '1px solid ' + (allOk ? '#b7e4c7' : '#f4cccc')});
                })
                .fail(function() { $tbody.html('<tr><td colspan="4" style="color:#d63638;">فشل الاتصال بالسيرفر.</td></tr>'); })
                .always(function() { $btn.prop('disabled', false).text('🔍 بدء الفحص التشخيصي'); $spin.removeClass('is-active'); });
        });
    });
    </script>
    <?php
}

/* ================================================================
 * 5. معالجات AJAX
 * ================================================================ */

/** حفظ الإعدادات العامة */
function uapp_ajax_save_general(): void
{
    check_ajax_referer( UAPP_NONCE_ACTION, 'nonce' );
    if ( ! current_user_can( UAPP_CAP ) ) wp_send_json_error( [ 'msg' => '🚫 صلاحية غير كافية.' ] );

    $s = uapp_get_settings();
    $s['maintenance_mode']  = ! empty( $_POST['maintenance_mode'] );
    $s['maintenance_title'] = sanitize_text_field( wp_unslash( $_POST['maintenance_title'] ?? '' ) );
    $s['maintenance_msg']   = sanitize_textarea_field( wp_unslash( $_POST['maintenance_msg'] ?? '' ) );
    $s['app_version']       = sanitize_text_field( wp_unslash( $_POST['app_version'] ?? '1.0.0' ) );
    $s['force_update_url']  = esc_url_raw( wp_unslash( $_POST['force_update_url'] ?? '' ) );
    $s['updated_at']        = time();

    update_option( UAPP_OPTION_KEY, $s );
    uapp_log_action('حفظ الإعدادات العامة');
    wp_send_json_success( [ 'msg' => '✅ تم الحفظ.', 'ts' => $s['updated_at'] ] );
}
add_action( 'wp_ajax_' . UAPP_AJAX_GENERAL, 'uapp_ajax_save_general' );

/** حفظ إعدادات الإعلانات */
function uapp_ajax_save_ads(): void
{
    check_ajax_referer( UAPP_NONCE_ACTION, 'nonce' );
    if ( ! current_user_can( UAPP_CAP ) ) wp_send_json_error( [ 'msg' => '🚫 صلاحية غير كافية.' ] );

    $s = uapp_get_settings();
    $s['admob_banner']       = ! empty( $_POST['admob_banner'] );
    $s['admob_interstitial'] = ! empty( $_POST['admob_interstitial'] );
    $s['admob_rewarded']     = ! empty( $_POST['admob_rewarded'] );
    $s['updated_at']         = time();

    update_option( UAPP_OPTION_KEY, $s );
    uapp_log_action('حفظ الإعدادات العامة');
    wp_send_json_success( [ 'msg' => '✅ تم الحفظ.', 'ts' => $s['updated_at'] ] );
}
add_action( 'wp_ajax_' . UAPP_AJAX_ADS, 'uapp_ajax_save_ads' );

/** التشخيص المباشر */
function uapp_ajax_run_diagnosis(): void
{
    check_ajax_referer( UAPP_NONCE_ACTION, 'nonce' );
    if ( ! current_user_can( UAPP_CAP ) ) wp_send_json_error( [ 'msg' => '🚫 صلاحية غير كافية.' ] );

    $results   = [];
    $rest_url  = rest_url( 'utility-app/v1/config' );

    // فحص PHP
    $results[] = [ 'label' => 'اتصال السيرفر', 'status' => true, 'detail' => 'PHP ' . phpversion() . ' — يعمل.' ];

    // فحص خيارات DB
    $opt = get_option( UAPP_OPTION_KEY );
    $results[] = [ 'label' => 'خيارات قاعدة البيانات', 'status' => $opt !== false,
        'detail' => $opt !== false ? 'موجودة وجاهزة.' : 'لم تُنشأ بعد (سيتم إنشاؤها عند أول حفظ).' ];

    // فحص REST داخلي
    $req  = new WP_REST_Request( 'GET', '/utility-app/v1/config' );
    $resp = rest_do_request( $req );
    $ok   = ! $resp->is_error() && isset( $resp->get_data()['status'] );
    $results[] = [ 'label' => 'REST API (داخلي)', 'status' => $ok,
        'detail' => $ok ? 'الاستجابة سليمة.' : 'لم تسجّل الـ Endpoint بعد. تأكد من وجود الكود المخصص.' ];

    // فحص REST خارجي
    $http = wp_remote_get( $rest_url, [ 'timeout' => 10, 'sslverify' => false ] );
    if ( is_wp_error( $http ) ) {
        $results[] = [ 'label' => 'REST API (خارجي)', 'status' => false, 'detail' => $http->get_error_message() ];
    } else {
        $code = wp_remote_retrieve_response_code( $http );
        $json = json_decode( wp_remote_retrieve_body( $http ), true );
        $results[] = [ 'label' => 'REST API (خارجي)', 'status' => $code === 200 && ! empty( $json['status'] ),
            'detail' => "HTTP $code — " . ( $code === 200 ? 'JSON سليم.' : 'استجابة غير متوقعة.' ) ];
    }

    // صلاحيات المجلد
    $dir = __DIR__;
    $results[] = [ 'label' => 'صلاحيات المجلد', 'status' => is_writable( $dir ),
        'detail' => is_writable( $dir ) ? 'المجلد قابل للكتابة.' : 'قد تحتاج لضبط الصلاحيات.' ];

    wp_send_json_success( [ 'msg' => 'اكتمل الفحص.', 'results' => $results ] );
}
add_action( 'wp_ajax_' . UAPP_AJAX_DIAG, 'uapp_ajax_run_diagnosis' );

/* ================================================================
 * 6. REST API Endpoint: /wp-json/utility-app/v1/config
 * ================================================================ */
function uapp_register_rest_api(): void {
    register_rest_route( 'utility-app/v1', '/config', [
        'methods'             => 'GET',
        'callback'            => 'uapp_rest_config',
        'permission_callback' => '__return_true',
    ] );
}
add_action( 'rest_api_init', 'uapp_register_rest_api' );

function uapp_rest_config(): WP_REST_Response {
    $s = uapp_get_settings();

    $data = [
        'status'             => true,
        'timestamp'          => $s['updated_at'],
        'maintenance_mode'   => (bool) $s['maintenance_mode'],
        'maintenance_title'  => $s['maintenance_mode'] ? $s['maintenance_title'] : '',
        'maintenance_msg'    => $s['maintenance_mode'] ? $s['maintenance_msg'] : '',
        'app_version'        => $s['app_version'],
        'min_app_version'    => '1.0.0',
        'force_update'       => (bool) ($s['force_update'] ?? false),
        'admob_enabled'      => (bool) $s['admob_banner'] || (bool) $s['admob_interstitial'] || (bool) $s['admob_rewarded'],
        'admob_banner'       => (bool) $s['admob_banner'],
        'admob_interstitial' => (bool) $s['admob_interstitial'],
        'admob_rewarded'     => (bool) $s['admob_rewarded'],
        'force_update_url'   => $s['force_update_url'] ?? '',
        'upcoming_events'    => array_map(function($e){return ['id'=>(int)$e['id'],'title_ar'=>$e['title_ar'],'hijri_date'=>$e['hijri_date'],'is_active'=>(bool)$e['is_active']];}, uapp_get_events()),
        'checksum'           => md5( json_encode( $s ) ),
    ];

    return new WP_REST_Response( $data, 200 );
}

/* ================================================================
 * 7. إدارة الأحداث القادمة
 * ================================================================ */
define( 'UAPP_EVENTS_KEY', 'utility_app_events' );

function uapp_default_events(): array {
    return [
        ['id'=>1,'title_ar'=>'رمضان المبارك','hijri_date'=>'1447-09-01','is_active'=>true],
        ['id'=>2,'title_ar'=>'عيد الفطر','hijri_date'=>'1447-10-01','is_active'=>true],
        ['id'=>3,'title_ar'=>'عيد الأضحى','hijri_date'=>'1447-12-10','is_active'=>true],
    ];
}

function uapp_get_events(): array {
    $events = get_option( UAPP_EVENTS_KEY, [] );
    return !empty($events) ? $events : uapp_default_events();
}

function uapp_render_events_tab(): void {
    $events = uapp_get_events();
    ?>
    <div class="uapp-card">
        <div class="uapp-card-title">📅 الأحداث القادمة</div>
        <p style="color:#646970;font-size:13px;">تظهر هذه الأحداث في تطبيق مِرساة مع عداد الأيام المتبقية.</p>
        <table class="widefat striped" style="margin-top:10px;">
            <thead><tr><th>ID</th><th>العنوان</th><th>التاريخ الهجري</th><th>نشط</th><th>حذف</th></tr></thead>
            <tbody id="uapp-events-tbody">
                <?php foreach($events as $e): ?>
                <tr data-id="<?php echo $e['id']; ?>">
                    <td><?php echo $e['id']; ?></td>
                    <td><input type="text" class="uapp-event-title" value="<?php echo esc_attr($e['title_ar']); ?>" style="width:180px;"></td>
                    <td><input type="text" class="uapp-event-date" value="<?php echo esc_attr($e['hijri_date']); ?>" placeholder="1447-09-01" style="width:120px;"></td>
                    <td><input type="checkbox" class="uapp-event-active" <?php checked($e['is_active']); ?>></td>
                    <td><button type="button" class="button button-small uapp-delete-event" style="color:#d63638;">✕</button></td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
        <p style="margin-top:8px;">
            <button type="button" id="uapp-add-event" class="button button-secondary">➕ إضافة حدث</button>
            <button type="button" id="uapp-save-events" class="button button-primary">💾 حفظ الأحداث</button>
            <span class="spinner" id="uapp-spinner-events" style="float:none;margin:0 8px;"></span>
        </p>
    </div>
    <script>
    jQuery(function($){
        $('#uapp-add-event').on('click',function(){
            $('#uapp-events-tbody').append('<tr data-id="'+Date.now()+'"><td>جديد</td><td><input type="text" class="uapp-event-title" style="width:180px;" placeholder="اسم الحدث"></td><td><input type="text" class="uapp-event-date" style="width:120px;" placeholder="1447-09-01"></td><td><input type="checkbox" class="uapp-event-active" checked></td><td><button class="button button-small uapp-delete-event" style="color:#d63638;">✕</button></td></tr>');
        });
        $(document).on('click','.uapp-delete-event',function(){$(this).closest('tr').remove();});
        $('#uapp-save-events').on('click',function(){
            var b=$(this),s=$('#uapp-spinner-events'),e=[];
            $('#uapp-events-tbody tr').each(function(){
                var r=$(this);
                e.push({id:parseInt(r.data('id')),title_ar:r.find('.uapp-event-title').val(),hijri_date:r.find('.uapp-event-date').val(),is_active:r.find('.uapp-event-active').is(':checked')});
            });
            b.prop('disabled',true).text('⏳');s.addClass('is-active');
            $.post(ajaxurl,{action:'uapp_save_events',nonce:'<?php echo wp_create_nonce(UAPP_NONCE_ACTION); ?>',events:JSON.stringify(e)})
            .done(function(r){alert(r.success?'✅ تم الحفظ':'❌ خطأ');})
            .always(function(){b.prop('disabled',false).text('💾 حفظ الأحداث');s.removeClass('is-active');});
        });
    });
    </script>
    <?php
}

function uapp_ajax_save_events_handler(): void {
    check_ajax_referer(UAPP_NONCE_ACTION,'nonce');
    if(!current_user_can(UAPP_CAP)) wp_send_json_error();
    $raw = wp_unslash($_POST['events']??'[]');
    $data = json_decode($raw,true);
    if(!is_array($data)) wp_send_json_error();
    $clean = [];
    foreach($data as $e){
        if(empty($e['title_ar'])||empty($e['hijri_date'])) continue;
        $clean[] = ['id'=>(int)($e['id']??time()),'title_ar'=>sanitize_text_field($e['title_ar']),'hijri_date'=>sanitize_text_field($e['hijri_date']),'is_active'=>(bool)($e['is_active']??true)];
    }
    update_option(UAPP_EVENTS_KEY,$clean);
    wp_send_json_success();
}
add_action('wp_ajax_uapp_save_events','uapp_ajax_save_events_handler');

/* ================================================================
 * 8. سجل النشاط
 * ================================================================ */
define('UAPP_LOG_KEY','utility_app_activity_log');

function uapp_log_action(string $action): void {
    $log = get_option(UAPP_LOG_KEY,[]);
    $log[] = ['time'=>time(),'action'=>$action,'user'=>wp_get_current_user()->user_login];
    if(count($log)>50) $log = array_slice($log,-50);
    update_option(UAPP_LOG_KEY,$log);
}

function uapp_render_activity_log(): void {
    $log = array_reverse(get_option(UAPP_LOG_KEY,[]));
    ?>
    <div class="uapp-card" style="margin-top:20px;">
        <div class="uapp-card-title">📋 آخر النشاطات</div>
        <?php if(empty($log)): ?>
            <p style="color:#646970;">لا توجد نشاطات بعد.</p>
        <?php else: ?>
            <table class="widefat striped">
                <thead><tr><th>الوقت</th><th>المستخدم</th><th>الإجراء</th></tr></thead>
                <tbody>
                <?php foreach(array_slice($log,0,10) as $entry): ?>
                    <tr>
                        <td><?php echo date('Y-m-d H:i',$entry['time']); ?></td>
                        <td><?php echo esc_html($entry['user']); ?></td>
                        <td><?php echo esc_html($entry['action']); ?></td>
                    </tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        <?php endif; ?>
    </div>
    <?php
}
