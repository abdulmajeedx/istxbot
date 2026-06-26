import { useState, useEffect, useCallback } from 'react';
import { settings, platforms, admin } from '../api/client';
import { useToast } from '../components/Toast';
import { PageSkeleton } from '../components/Skeleton';
import { Save, Shield, Settings2, Layers, Globe, Bell, Lock, Key } from 'lucide-react';

const TABS = [
  { key: 'general', label: 'عام', icon: Settings2 },
  { key: 'platforms', label: 'المنصات', icon: Layers },
  { key: 'tiers', label: 'المستويات', icon: Shield },
  { key: 'security', label: 'الحماية', icon: Lock },
];

export default function SettingsPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState('general');
  const [generalSettings, setGeneralSettings] = useState({});
  const [platformList, setPlatformList] = useState({});
  const [tierLimits, setTierLimits] = useState({});

  const [saving, setSaving] = useState(false);
  const [adminPwd, setAdminPwd] = useState('');
  const [pwdConfirm, setPwdConfirm] = useState('');

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [gRes, pRes, tRes] = await Promise.all([
        settings.general.get(),
        platforms.get(),
        settings.tierLimits.get(),
      ]);
      setGeneralSettings(gRes.data?.settings || gRes.data || {});
      setPlatformList(pRes.data?.platforms || pRes.data || {});
      setTierLimits(tRes.data?.limits || tRes.data || {});
    } catch (err) {
      toast.error('فشل تحميل الإعدادات');
    }
    setLoading(false);
  }, [toast]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleSave = async (type, data) => {
    setSaving(true);
    try {
      if (type === 'general') await settings.general.update(data);
      else if (type === 'platforms') await platforms.update(data);
      else if (type === 'tiers') await settings.tierLimits.update(data);
      toast.success('تم حفظ الإعدادات بنجاح');
    } catch (err) {
      toast.error('فشل حفظ الإعدادات');
    }
    setSaving(false);
  };

  const handleChangePwd = async () => {
    if (!adminPwd || adminPwd.length < 6) {
      toast.warning('كلمة المرور يجب أن تكون 6 أحرف على الأقل');
      return;
    }
    if (adminPwd !== pwdConfirm) {
      toast.warning('كلمتا المرور غير متطابقتين');
      return;
    }
    try {
      await admin.changePassword(adminPwd);
      setAdminPwd('');
      setPwdConfirm('');
      toast.success('تم تغيير كلمة المرور بنجاح');
    } catch (err) {
      toast.error('فشل تغيير كلمة المرور');
    }
  };

  if (loading) return <PageSkeleton />;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">الإعدادات</h2>
        <p className="text-slate-500 text-sm mt-1">تحكم كامل في إعدادات البوت</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${
              tab === key ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/25' : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            <Icon className="w-4 h-4" /> {label}
          </button>
        ))}
      </div>

      {/* General Settings */}
      {tab === 'general' && (
        <div className="card space-y-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Globe className="w-5 h-5 text-indigo-400" />
            الإعدادات العامة
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { key: 'max_file_size_mb', label: 'حجم الملف الأقصى (MB)', type: 'number' },
              { key: 'max_downloads_per_day', label: 'التحميلات اليومية القصوى', type: 'number' },
              { key: 'download_timeout', label: 'مهلة التحميل (ثانية)', type: 'number' },
              { key: 'concurrent_downloads', label: 'التحميلات المتزامنة', type: 'number' },
              { key: 'hd_quality_enabled', label: 'جودة HD', type: 'checkbox' },
              { key: 'ads_enabled', label: 'الإعلانات', type: 'checkbox' },
              { key: 'maintenance_mode', label: 'وضع الصيانة', type: 'checkbox' },
              { key: 'background_download', label: 'تحميل بالخلفية', type: 'checkbox' },
              { key: 'mp3_conversion', label: 'تحويل MP3', type: 'checkbox' },
              { key: 'watermark_removal', label: 'إزالة العلامة المائية', type: 'checkbox' },
            ].map(({ key, label, type }) => (
              <div key={key}>
                <label className="block text-sm text-slate-400 mb-1.5">{label}</label>
                {type === 'checkbox' ? (
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox" checked={!!generalSettings[key]}
                      onChange={(e) => setGeneralSettings({ ...generalSettings, [key]: e.target.checked })}
                      className="w-5 h-5 rounded accent-indigo-600 focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-slate-900"
                    />
                    <span className={`text-xs font-medium transition-colors ${generalSettings[key] ? 'text-emerald-400' : 'text-slate-500'}`}>
                      {generalSettings[key] ? 'مفعل' : 'معطل'}
                    </span>
                  </label>
                ) : (
                  <input
                    type={type || 'text'} className="input-field"
                    value={generalSettings[key] || ''}
                    onChange={(e) => setGeneralSettings({ ...generalSettings, [key]: type === 'number' ? (parseInt(e.target.value) || 0) : e.target.value })}
                    dir="ltr"
                  />
                )}
              </div>
            ))}
          </div>
          <button onClick={() => handleSave('general', generalSettings)} disabled={saving} className="btn btn-primary">
            <Save className="w-4 h-4" /> حفظ الإعدادات العامة
          </button>
        </div>
      )}

      {/* Platforms */}
      {tab === 'platforms' && (
        <div className="card space-y-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Layers className="w-5 h-5 text-indigo-400" />
            إعدادات المنصات
          </h3>
          <div className="space-y-3">
            {Object.entries(platformList).length === 0 ? (
              <p className="text-slate-500 text-sm py-4 text-center">لا توجد منصات مضافة</p>
            ) : (
              Object.entries(platformList).map(([name, config]) => (
                <div key={name} className="flex items-center justify-between p-4 bg-slate-800/50 rounded-xl flex-wrap gap-3 hover:bg-slate-800/70 transition-colors">
                  <span className="font-medium text-white min-w-[80px]">{name}</span>
                  <div className="flex items-center gap-4 flex-wrap">
                    <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
                      <input type="checkbox" checked={config?.enabled !== false}
                        onChange={() => setPlatformList({ ...platformList, [name]: { ...config, enabled: !(config?.enabled !== false) } })}
                        className="w-4 h-4 rounded accent-indigo-600 focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-slate-900" />
                      مفعّل
                    </label>
                    <div className="flex items-center gap-2">
                      <input type="number" className="input-field w-20 text-center" placeholder="حد"
                        value={config?.daily_limit || ''}
                        onChange={(e) => setPlatformList({ ...platformList, [name]: { ...config, daily_limit: parseInt(e.target.value) || 0 } })} dir="ltr" />
                      <span className="text-xs text-slate-500">/يوم</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
          <button onClick={() => handleSave('platforms', platformList)} disabled={saving} className="btn btn-primary">
            <Save className="w-4 h-4" /> حفظ المنصات
          </button>
        </div>
      )}

      {/* Tiers */}
      {tab === 'tiers' && (
        <div className="card space-y-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Shield className="w-5 h-5 text-indigo-400" />
            حدود المستويات
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {['free', 'premium', 'vip'].map((tier) => (
              <div key={tier} className="bg-slate-800/50 rounded-xl p-4 space-y-3 hover:bg-slate-800/70 transition-colors">
                <h4 className="font-semibold text-white capitalize">{tier}</h4>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">التحميلات اليومية</label>
                  <input type="number" className="input-field" value={tierLimits[tier]?.daily || ''}
                    onChange={(e) => setTierLimits({ ...tierLimits, [tier]: { ...tierLimits[tier], daily: parseInt(e.target.value) || 0 } })} dir="ltr" />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">حجم الملف (MB)</label>
                  <input type="number" className="input-field" value={tierLimits[tier]?.max_file_size || ''}
                    onChange={(e) => setTierLimits({ ...tierLimits, [tier]: { ...tierLimits[tier], max_file_size: parseInt(e.target.value) || 0 } })} dir="ltr" />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">الأولوية</label>
                  <input type="number" className="input-field" value={tierLimits[tier]?.priority || ''}
                    onChange={(e) => setTierLimits({ ...tierLimits, [tier]: { ...tierLimits[tier], priority: parseInt(e.target.value) || 0 } })} dir="ltr" />
                </div>
              </div>
            ))}
          </div>
          <button onClick={() => handleSave('tiers', tierLimits)} disabled={saving} className="btn btn-primary">
            <Save className="w-4 h-4" /> حفظ المستويات
          </button>
        </div>
      )}

      {/* Security */}
      {tab === 'security' && (
        <div className="space-y-6">
          <div className="card space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Key className="w-5 h-5 text-indigo-400" />
              تغيير كلمة المرور
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1.5">كلمة المرور الجديدة</label>
                <input type="password" className="input-field" placeholder="••••••••" value={adminPwd} onChange={(e) => setAdminPwd(e.target.value)} dir="ltr" />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1.5">تأكيد كلمة المرور</label>
                <input type="password" className="input-field" placeholder="••••••••" value={pwdConfirm} onChange={(e) => setPwdConfirm(e.target.value)} dir="ltr" />
              </div>
            </div>
            <button onClick={handleChangePwd} className="btn btn-primary">
              <Save className="w-4 h-4" /> تغيير كلمة المرور
            </button>
          </div>
          <div className="card space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Bell className="w-5 h-5 text-indigo-400" />
              إعدادات الأمان
            </h3>
            <div className="space-y-3">
              {[
                { key: 'two_factor_auth', label: 'التحقق بخطوتين (2FA)', desc: 'يتطلب رمز تحقق عبر تيليجرام عند تسجيل الدخول' },
                { key: 'login_notifications', label: 'إشعارات تسجيل الدخول', desc: 'إرسال إشعار عند كل تسجيل دخول للوحة التحكم' },
                { key: 'ip_whitelist', label: 'قائمة IP البيضاء', desc: 'تقييد الدخول للوحة التحكم بعناوين IP محددة' },
              ].map(({ key, label, desc }) => (
                <div key={key} className="flex items-start justify-between p-4 bg-slate-800/50 rounded-xl hover:bg-slate-800/70 transition-colors">
                  <div>
                    <p className="text-sm font-medium text-white">{label}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer shrink-0">
                    <input type="checkbox" className="sr-only peer" defaultChecked={key === 'two_factor_auth'} />
                    <div className="w-9 h-5 bg-slate-700 peer-focus:ring-2 peer-focus:ring-indigo-500 rounded-full peer peer-checked:after:translate-x-4 after:content-[''] after:absolute after:top-[2px] after:right-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600" />
                  </label>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

