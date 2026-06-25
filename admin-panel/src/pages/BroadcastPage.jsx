import { useState } from 'react';
import { admin, stats } from '../api/client';
import { useToast } from '../components/Toast';
import { Send, Users, Eye, Loader2 } from 'lucide-react';

export default function BroadcastPage() {
  const { toast } = useToast();
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [preview, setPreview] = useState(false);
  const [sentCount, setSentCount] = useState(null);

  const handleSend = async () => {
    if (!message.trim()) {
      toast.warning('الرجاء كتابة نص الرسالة');
      return;
    }

    setSending(true);
    try {
      const { data } = await admin.broadcast(message.trim());
      setSentCount(data?.recipients || data?.count || 'تم');
      toast.success(`تم إرسال الرسالة بنجاح`);
      setMessage('');
    } catch (err) {
      toast.error(err.response?.data?.message || 'فشل إرسال الرسالة');
    }
    setSending(false);
  };

  const previewMsg = message
    .replace(/<b>/g, '<b>')
    .replace(/<\/b>/g, '</b>')
    .replace(/<i>/g, '<i>')
    .replace(/<\/i>/g, '</i>');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">رسالة جماعية</h2>
        <p className="text-slate-500 text-sm mt-1">إرسال إشعار أو تحديث لجميع مستخدمي البوت</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Compose */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Send className="w-5 h-5 text-indigo-400" />
              كتابة الرسالة
            </h3>

            <div>
              <label className="block text-sm text-slate-400 mb-1.5">نص الرسالة</label>
              <textarea
                className="input-field h-48 resize-y"
                placeholder="اكتب رسالتك هنا... يمكنك استخدام تنسيق HTML بسيط مثل <b>غامق</b> و <i>مائل</i>"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                dir="rtl"
              />
              <p className="text-xs text-slate-600 mt-1.5">{message.length} حرف</p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleSend}
                disabled={sending || !message.trim()}
                className="btn btn-primary flex items-center gap-2"
              >
                {sending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    جاري الإرسال...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    إرسال للجميع
                  </>
                )}
              </button>
              <button
                onClick={() => setPreview(!preview)}
                className="btn btn-ghost flex items-center gap-2"
              >
                <Eye className="w-4 h-4" />
                {preview ? 'إخفاء المعاينة' : 'معاينة'}
              </button>
            </div>

            {sentCount !== null && (
              <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-4 py-3 text-sm text-emerald-400">
                ✅ تم إرسال الرسالة بنجاح{sentCount !== 'تم' && ` إلى ${sentCount} مستخدم`}
              </div>
            )}
          </div>

          {/* Preview */}
          {preview && message && (
            <div className="card space-y-3">
              <h3 className="text-sm font-semibold text-slate-400 flex items-center gap-2">
                <Eye className="w-4 h-4" />
                معاينة الرسالة
              </h3>
              <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/30">
                <div
                  className="text-white text-sm leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: previewMsg.replace(/\n/g, '<br/>') }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Info sidebar */}
        <div className="space-y-4">
          <div className="card space-y-3">
            <h3 className="text-sm font-semibold text-slate-400 flex items-center gap-2">
              <Users className="w-4 h-4 text-indigo-400" />
              معلومات
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">المستلمون</span>
                <span className="text-white font-medium">جميع المستخدمين</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">التنسيق</span>
                <span className="text-white font-medium">HTML مدعوم</span>
              </div>
            </div>
          </div>

          <div className="card bg-amber-500/5 border-amber-500/20 space-y-2">
            <h3 className="text-sm font-semibold text-amber-400">⚠️ تنبيه</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              سيتم إرسال الرسالة لجميع مستخدمي البوت دفعة واحدة. تأكد من محتوى الرسالة قبل الإرسال.
              لا يمكن التراجع عن الإرسال.
            </p>
          </div>

          <div className="card space-y-2">
            <h3 className="text-sm font-semibold text-slate-400">تنسيقات مدعومة</h3>
            <div className="space-y-1 text-xs text-slate-500 font-mono" dir="ltr">
              <p><code className="text-indigo-400">&lt;b&gt;</code>bold<code className="text-indigo-400">&lt;/b&gt;</code> — <b>غامق</b></p>
              <p><code className="text-indigo-400">&lt;i&gt;</code>italic<code className="text-indigo-400">&lt;/i&gt;</code> — <i>مائل</i></p>
              <p><code className="text-indigo-400">&lt;code&gt;</code>code<code className="text-indigo-400">&lt;/code&gt;</code> — <code>برمجي</code></p>
              <p><code className="text-indigo-400">&lt;a href="..."&gt;</code>link<code className="text-indigo-400">&lt;/a&gt;</code> — رابط</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
