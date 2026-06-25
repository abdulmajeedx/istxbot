jQuery(function($) {

    // ============ Tabs ============
    $('.tdl-tab').on('click', function() {
        var tab = $(this).data('tab');
        $('.tdl-tab').removeClass('active');
        $(this).addClass('active');
        $('.tdl-tab-content').removeClass('active');
        $('.tdl-tab-content[data-tab="' + tab + '"]').addClass('active');
    });

    // ============ Toast Notification ============
    function showToast(msg, type) {
        var t = $('#tdl-toast');
        t.removeClass('success error info').addClass(type).text(msg).fadeIn(300);
        clearTimeout(t.data('timer'));
        t.data('timer', setTimeout(function() { t.fadeOut(400); }, 3000));
    }

    // ============ AJAX Save ============
    $('.tdl-tab-content form, form.tdl-tab-content').on('submit', function(e) {
        e.preventDefault();
        var form = $(this);
        var btn = form.find('button[type="submit"]');
        var origText = btn.text();

        btn.prop('disabled', true).html('<span class="tdl-spinner"></span> جاري الحفظ...');

        var data = form.serializeArray();
        data.push({name: 'action', value: 'tdl_save_settings'});
        data.push({name: '_ajax_nonce', value: TDL.nonce});

        $.post(TDL.ajax_url, $.param(data), function(resp) {
            if (resp.success) {
                showToast(resp.data.message || 'تم الحفظ', 'success');
            } else {
                showToast(resp.data.message || 'فشل الحفظ', 'error');
            }
        }).fail(function() {
            showToast('خطأ في الاتصال', 'error');
        }).always(function() {
            btn.prop('disabled', false).text(origText);
        });
    });

    // ============ Health Check ============
    $('#tdl-health-btn').on('click', function() {
        var btn = $(this);
        var spinner = $('#tdl-health-spinner');
        var result = $('#tdl-health-result');

        btn.prop('disabled', true);
        spinner.show();
        result.hide();

        $.post(TDL.ajax_url, {
            action: 'tdl_health_check',
            _ajax_nonce: TDL.nonce
        }, function(resp) {
            if (resp.success) {
                var html = '<div style="margin-bottom:8px;color:#4cd964">✅ API Status: Healthy</div>';
                html += '<div style="color:#71717a;font-size:11px">' + resp.data.time + '</div>';
                $.each(resp.data.checks, function(k, v) {
                    var c = v.status === 'ok' ? '#4cd964' : (v.status === 'error' ? '#ef4444' : '#f59e0b');
                    html += '<div style="color:' + c + '">' + k + ': ' + v.status + (v.version ? ' (' + v.version + ')' : '') + '</div>';
                });
                result.html(html).show();
            } else {
                result.html('<div style="color:#ef4444">❌ فشل الفحص</div>').show();
            }
        }).fail(function() {
            result.html('<div style="color:#ef4444">❌ خطأ في الاتصال</div>').show();
        }).always(function() {
            btn.prop('disabled', false);
            spinner.hide();
        });
    });

    // ============ Scraper Test ============
    $('#tdl-scrape-btn').on('click', function() {
        var btn = $(this);
        var url = $('#tdl-scrape-url').val().trim();
        var result = $('#tdl-scrape-result');

        if (!url) { showToast('الرجاء إدخال رابط TikTok', 'error'); return; }

        btn.prop('disabled', true).text('⏳ جاري الفحص...');
        result.hide();

        $.post(TDL.ajax_url, {
            action: 'tdl_scrape_test',
            url: url,
            _ajax_nonce: TDL.nonce
        }, function(resp) {
            if (resp.success) {
                var d = resp.data;
                var html = '<div style="margin-bottom:10px;font-weight:bold;color:' + (d.success ? '#4cd964' : '#ef4444') + '">' +
                    (d.success ? '✅ نجح الكشط' : '❌ فشل الكشط') + ' (' + d.duration_ms + 'ms)</div>';

                if (d.video_url) {
                    html += '<div style="margin-bottom:8px"><span style="color:#71717a">الرابط: </span><span style="color:#00f2ea;word-break:break-all;font-size:11px">' + d.video_url + '</span></div>';
                }
                if (d.error) {
                    html += '<div style="color:#ef4444;margin-bottom:8px">❌ ' + d.error + '</div>';
                }

                $.each(d.steps, function(i, s) {
                    html += '<div class="step ' + (s.passed ? 'pass' : 'fail') + '">' + (i+1) + '. ' + (s.message || s.name) + '</div>';
                    if (s.found) html += '<div class="found-url">→ ' + s.found + '</div>';
                });

                result.html(html).show();
            } else {
                showToast(resp.data.message || 'فشل الفحص', 'error');
            }
        }).fail(function() {
            showToast('خطأ في الاتصال', 'error');
        }).always(function() {
            btn.prop('disabled', false).text('🔍 فحص الرابط');
        });
    });

    // ============ Push Notification ============
    $('#tdl-push-btn').on('click', function() {
        var btn = $(this);
        var spinner = $('#tdl-push-spinner');

        var title  = $('#tdl-push-title').val().trim();
        var body   = $('#tdl-push-body').val().trim();
        var url    = $('#tdl-push-url').val().trim();
        var target = $('#tdl-push-target').val();

        if (!title && !url) { showToast('العنوان أو الرابط مطلوب', 'error'); return; }

        btn.prop('disabled', true);
        spinner.show();

        $.post(TDL.ajax_url, {
            action: 'tdl_send_push',
            title: title, body: body, url: url, target: target,
            _ajax_nonce: TDL.nonce
        }, function(resp) {
            if (resp.success) {
                showToast('✅ تم الإرسال: ' + resp.data.sent + ' نجاح, ' + resp.data.failed + ' فشل', 'success');
            } else {
                showToast(resp.data.message || 'فشل الإرسال', 'error');
            }
        }).fail(function() {
            showToast('خطأ في الاتصال', 'error');
        }).always(function() {
            btn.prop('disabled', false);
            spinner.hide();
        });
    });

});
