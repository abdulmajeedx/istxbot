import { useState, useEffect, useCallback } from 'react';
import {
  X, Download, MapPin, Globe, Smartphone, Calendar, Clock, Activity,


} from 'lucide-react';
import { users, admin } from '../api/client';
import { useToast } from './Toast';
import TierBadge from './TierBadge';

const tierColor = {
  vip: 'from-amber-500 to-orange-600',
  premium: 'from-indigo-500 to-purple-600',
  free: 'from-slate-500 to-slate-600',
};

const tierLabel = { free: 'مجاني', premium: 'بريميوم', vip: 'VIP' };

const DURATION_OPTIONS = [
  { value: null, label: 'دائم 🔒' },
  { value: 86400, label: '24 ساعة' },
  { value: 604800, label: '7 أيام' },
  { value: 2592000, label: '30 يوم' },
  { value: 'custom', label: '🗓️ تاريخ محدد' },
];

export default function UserDetailPanel({ user, onClose, onRefresh, ghostMode = false }) {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState('overview');

  const [detail, setDetail] = useState(null);
  const [acting, setActing] = useState(false);
  const [banReason, setBanReason] = useState('');

  const [msgText, setMsgText] = useState('');


  // Tier management

  const [selectedTier, setSelectedTier] = useState('free');
  const [durationOption, setDurationOption] = useState(null);
  const [customDate, setCustomDate] = useState('');

  const loadDetail = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const { data } = await users.detail(user.user_id);
      if (data?.success) {
        setDetail(data.user);
        setSelectedTier((data.user.tier || 'free').toLowerCase());
      } else {
        setDetail(null);
      }
    } catch {
      setDetail(null);
    }
    setLoading(false);
  }, [user]);

  useEffect(() => { loadDetail(); }, [loadDetail]);

  const u = detail || user;
  const isBanned = u?.is_banned;
  const currentTier = (u?.tier || 'free').toLowerCase();
  const remainingSeconds = u?.remaining_seconds;
  const tierExpiresAt = u?.tier_expires_at;

  const formatRemaining = (secs) => {
    if (secs == null) return 'دائمة 🔒';
    if (secs <= 0) return 'منتهية ❌';
    const days = Math.floor(secs / 86400);
    const hours = Math.floor((secs % 86400) / 3600);
    if (days > 0) return `باقي ${days} يوم`;
    if (hours > 0) return `باقي ${hours} ساعة`;
    return 'باقي أقل من ساعة';
  };

  const handleBan = async () => {
    setActing(true);
    try {
      if (isBanned) {
        await users.unban(user.user_id);
        toast.success('تم فك الحظر');
      } else {
        await users.ban(user.user_id, banReason);
        toast.success('تم حظر المستخدم');
        setBanReason('');
      }
      setShowBanInput(false);
      loadDetail();
      onRefresh?.();
    } catch { toast.error('فشل تنفيذ الإجراء'); }
    setActing(false);
  };

  const handlePromote = async () => {
    if (selectedTier === currentTier && durationOption === null && !customDate) return;
    setActing(true);
    try {
      let expiresIn = durationOption;
      if (durationOption === 'custom' && customDate) {
        const target = new Date(customDate).getTime() / 1000;
        expiresIn = Math.max(60, Math.round(target - Date.now() / 1000));
      }

      if (ghostMode) {
        // في وضع الشبح: استخدام ghost API الصامت مع دعم الإنزال والترقية
        const { data } = await admin.ghostSetTier(user.user_id, selectedTier, expiresIn);
        toast.success(data?.message || 'تم حفظ التغييرات (وضع الشبح)');
      } else {
        const { data } = await users.setTier(user.user_id, selectedTier, expiresIn);
        toast.success(data?.message || 'تم حفظ التغييرات');
      }

      // تنظيف واجهة محرر المستوى - التغيير حُفظ بنجاح
      setShowTierEditor(false);
      setDurationOption(null);
      setCustomDate('');
      setActing(false);

      // تحديث البيانات في الخلفية - فشلها لا يعني فشل الحفظ
      try {
        await loadDetail();
        onRefresh?.();
      } catch (e) {
        // فشل تحديث الواجهة فقط، التغيير حُفظ بنجاح في قاعدة البيانات
        console.warn('[GhostMode] فشل تحديث الواجهة بعد الحفظ:', e);
      }
    } catch (err) {
      console.error('[GhostMode] فشل حفظ التغيير:', err);
      toast.error('فشل حفظ التغييرات');
      setActing(false);
    }
  };

  const handleRevoke = async () => {
    setActing(true);
    try {
      const { data } = await admin.revokeTier(user.user_id);
      toast.success(data?.message || 'تم إلغاء الصلاحية');
      setShowTierEditor(false);
      loadDetail();
      onRefresh?.();
    } catch { toast.error('فشل إلغاء الصلاحية'); }
    setActing(false);
  };

  const handleSendMsg = async () => {
    if (!msgText.trim()) return;
    setActing(true);
    try {
      await admin.sendMessage(user.user_id, msgText);
      toast.success('تم إرسال الرسالة');
      setMsgText('');
      setShowMsgInput(false);
    } catch { toast.error('فشل إرسال الرسالة'); }
    setActing(false);
  };

  if (!u) return null;

  const tabClasses = (tab) =>
    `px-3 py-2 text-xs font-medium rounded-lg transition-colors ${
      activeTab === tab
        ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-600/30'
        : 'text-slate-400 hover:text-white'
    }`;

  const avatarInitial = (u.first_name || u.username || user.user_id?.toString() || '?')[0]?.toUpperCase();

  const minDate = new Date(Date.now() + 86400000).toISOString().split('T')[0];

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-lg bg-slate-900 border-l border-slate-800 h-full overflow-y-auto shadow-2xl animate-in slide-in-from-right"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-slate-900/95 backdrop-blur-sm border-b border-slate-800 z-10">
          <div className="p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-12 h-12 rounded-full bg-gradient-to-br ${tierColor[currentTier] || tierColor.free} flex items-center justify-center text-lg font-bold ring-2 ring-white/10`}>
                {avatarInitial}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-white">{u.first_name || u.username || `#${u.user_id}`}</h3>
                  <TierBadge tier={currentTier} />
                </div>
                <p className="text-xs text-slate-500">
                  {u.username ? `@${u.username}` : ''}
                  {u.username && u.user_id ? ' — ' : ''}
                  {u.user_id ? `#${u.user_id}` : ''}
                </p>
              </div>
            </div>
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Quick Actions */}
          <div className="flex gap-1.5 px-4 pb-3">
            {isBanned ? (
              <button onClick={handleBan} disabled={acting} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-xs font-medium transition-colors border border-emerald-500/20">
                <ShieldOff className="w-3.5 h-3.5" />
                فك الحظر
              </button>
            ) : (
              <button onClick={() => setShowBanInput(true)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 text-xs font-medium transition-colors border border-red-500/20">
                <Ban className="w-3.5 h-3.5" />
                حظر
              </button>
            )}
            <button onClick={() => { setShowTierEditor(true); setSelectedTier(currentTier); }} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 text-xs font-medium transition-colors border border-amber-500/20">
              <Crown className="w-3.5 h-3.5" />
              إدارة الصلاحية
            </button>
            <button onClick={() => setShowMsgInput(true)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/10 text-sky-400 hover:bg-sky-500/20 text-xs font-medium transition-colors border border-sky-500/20">
              <MessageSquare className="w-3.5 h-3.5" />
              مراسلة
            </button>
          </div>

          {/* Ban reason input */}
          {showBanInput && (
            <div className="px-4 pb-3 border-t border-slate-800 pt-3">
              <textarea
                className="input-field h-20 mb-2 text-sm"
                placeholder="سبب الحظر (سيُرسل للمستخدم)..."
                value={banReason}
                onChange={(e) => setBanReason(e.target.value)}
                autoFocus
              />
              <div className="flex gap-2">
                <button onClick={handleBan} disabled={acting || !banReason.trim()} className="btn btn-danger text-xs px-4 py-1.5">
                  {acting ? 'جاري...' : 'تأكيد الحظر'}
                </button>
                <button onClick={() => { setShowBanInput(false); setBanReason(''); }} className="btn btn-ghost text-xs px-4 py-1.5">إلغاء</button>
              </div>
            </div>
          )}

          {/* Message input */}
          {showMsgInput && (
            <div className="px-4 pb-3 border-t border-slate-800 pt-3">
              <textarea
                className="input-field h-20 mb-2 text-sm"
                placeholder="نص الرسالة..."
                value={msgText}
                onChange={(e) => setMsgText(e.target.value)}
                autoFocus
              />
              <div className="flex gap-2">
                <button onClick={handleSendMsg} disabled={acting || !msgText.trim()} className="btn btn-primary text-xs px-4 py-1.5">
                  {acting ? 'جاري...' : 'إرسال'}
                </button>
                <button onClick={() => { setShowMsgInput(false); setMsgText(''); }} className="btn btn-ghost text-xs px-4 py-1.5">إلغاء</button>
              </div>
            </div>
          )}

          {/* Tier Editor */}
          {showTierEditor && (
            <div className="px-4 pb-3 border-t border-slate-800 pt-3 space-y-3">
              {/* ═══ Ghost Mode Banner داخل محرر المستوى ═══ */}
              {ghostMode && (
                <div className="flex items-center gap-2 p-2.5 rounded-lg bg-indigo-600/10 border border-indigo-600/20 text-indigo-400 text-xs">
                  <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                  <span>وضع الشبح مفعل - لن يتم إشعار المستخدم بهذا التغيير</span>
                </div>
              )}

              <div>
                <label className="block text-xs text-slate-400 mb-1.5">المستوى</label>
                <div className="flex gap-2">
                  {['free', 'premium', 'vip'].map((t) => (
                    <button
                      key={t}
                      onClick={() => setSelectedTier(t)}
                      className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${
                        selectedTier === t
                          ? ghostMode
                            ? 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30'
                            : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                          : 'bg-slate-800 text-slate-400 border-slate-700 hover:border-slate-600'
                      }`}
                    >
                      {tierLabel[t]}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1.5">مدة الصلاحية</label>
                <div className="flex flex-wrap gap-1.5">
                  {DURATION_OPTIONS.map((opt) => (
                    <button
                      key={opt.label}
                      onClick={() => setDurationOption(opt.value)}
                      className={`px-2.5 py-1.5 rounded-lg text-xs border transition-colors ${
                        durationOption === opt.value
                          ? ghostMode
                            ? 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30'
                            : 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30'
                          : 'bg-slate-800 text-slate-400 border-slate-700 hover:border-slate-600'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                {durationOption === 'custom' && (
                  <input
                    type="date"
                    min={minDate}
                    value={customDate}
                    onChange={(e) => setCustomDate(e.target.value)}
                    className="input-field mt-2 text-sm"
                    dir="ltr"
                  />
                )}
              </div>

              <div className="flex gap-2 pt-1">
                <button
                  onClick={handlePromote}
                  disabled={acting}
                  className={`flex-1 btn text-xs py-2 ${
                    ghostMode
                      ? 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white border-0'
                      : 'btn-primary'
                  }`}
                >
                  {acting ? 'جاري...' : (
                    <span className="flex items-center justify-center gap-1.5">
                      {ghostMode ? <Ghost className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
                      {ghostMode ? 'حفظ بصمت' : 'حفظ التغييرات'}
                    </span>
                  )}
                </button>
                {currentTier !== 'free' && (
                  <button onClick={handleRevoke} disabled={acting} className="btn btn-danger text-xs py-2">
                    <RotateCcw className="w-3.5 h-3.5" />
                  </button>
                )}
                <button onClick={() => { setShowTierEditor(false); setDurationOption(null); setCustomDate(''); }} className="btn btn-ghost text-xs py-2">إلغاء</button>
              </div>
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-2 px-4 pb-3">
            <button onClick={() => setActiveTab('overview')} className={tabClasses('overview')}>عام</button>
            <button onClick={() => setActiveTab('downloads')} className={tabClasses('downloads')}>التحميلات ({u.downloads?.length || 0})</button>
            <button onClick={() => setActiveTab('activity')} className={tabClasses('activity')}>النشاط</button>
          </div>
        </div>

        {loading ? (
          <div className="p-8 space-y-4 animate-pulse">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-5 skeleton rounded" />
            ))}
          </div>
        ) : activeTab === 'overview' ? (
          <div className="p-4 space-y-4">
            {/* Ban alert */}
            {isBanned ? (
              <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                هذا المستخدم محظور
              </div>
            ) : null}

            {/* Tier Status */}
            <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/15">
              <div className="flex items-center gap-2 mb-1">
                <ClockIcon className="w-4 h-4 text-amber-400" />
                <span className="text-xs text-amber-400">حالة الصلاحية</span>
              </div>
              <p className="text-sm text-amber-300">{formatRemaining(remainingSeconds)}</p>
              {tierExpiresAt && (
                <p className="text-xs text-slate-500 mt-0.5">
                  حتى {new Date(tierExpiresAt * 1000).toLocaleDateString('ar-SA')}
                </p>
              )}
            </div>

            {/* Main stats grid */}
            <div className="grid grid-cols-2 gap-3">
              <InfoCard icon={MapPin} label="الدولة" value={u.country || '—'} />
              <InfoCard icon={Globe} label="اللغة" value={u.language_code || '—'} />
              <InfoCard icon={Smartphone} label="عدد الزيارات" value={String(u.visit_count || 0)} />
              <InfoCard icon={Download} label="إجمالي التحميلات" value={String(u.total_downloads || 0)} />
              <InfoCard icon={Activity} label="تحميلات اليوم" value={`${u.daily_count || 0} / ${u.daily_limit || 0}`} />
              <InfoCard icon={Zap} label="النقاط" value={String(u.points ?? 0)} />
              <InfoCard icon={Calendar} label="أول زيارة" value={u.first_visit ? new Date(u.first_visit).toLocaleDateString('ar-SA') : '—'} />
              <InfoCard icon={Clock} label="آخر زيارة" value={u.last_visit ? new Date(u.last_visit).toLocaleDateString('ar-SA') : '—'} />
            </div>

            {/* Status badge */}
            <div className="flex items-center gap-2 p-3 rounded-xl bg-slate-800/50 border border-slate-700/50">
              <div className={`w-2.5 h-2.5 rounded-full ${u.status === 'active' ? 'bg-emerald-500' : u.status === 'banned' ? 'bg-red-500' : 'bg-slate-500'}`} />
              <span className="text-sm text-slate-300">
                {u.status === 'active' ? 'نشط' : u.status === 'banned' ? 'محظور' : u.status || 'غير معروف'}
              </span>
              {u.is_premium ? (
                <span className="mr-auto flex items-center gap-1 text-xs text-amber-400">
                  <Star className="w-3 h-3" /> Premium Telegram
                </span>
              ) : null}
            </div>

            {/* User ID */}
            <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50">
              <p className="text-xs text-slate-500 mb-1">المعرف (User ID)</p>
              <p className="text-sm font-mono text-white">{u.user_id}</p>
            </div>
          </div>
        ) : activeTab === 'downloads' ? (
          <div className="p-4 space-y-3">
            {u.downloads?.length > 0 ? (
              u.downloads.map((d, i) => (
                <div key={i} className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50 hover:bg-slate-800/70 transition-colors">
                  <div className="flex items-center justify-between mb-1">
                    <span className="flex items-center gap-1.5 text-sm font-medium text-white">
                      <Download className="w-3.5 h-3.5 text-indigo-400" />
                      {d.platform || '—'}
                    </span>
                    <span className="text-xs text-slate-500">
                      {d.downloaded_at ? new Date(d.downloaded_at).toLocaleString('ar-SA') : '—'}
                    </span>
                  </div>
                  {d.title && <p className="text-xs text-slate-400 truncate mt-1">{d.title}</p>}
                  {d.file_size && <p className="text-xs text-slate-500 mt-1">{Math.round(d.file_size / 1024)} KB</p>}
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500 text-center py-12">لا توجد تحميلات</p>
            )}
          </div>
        ) : (
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <InfoCard icon={Download} label="تحميلات اليوم" value={String(u.daily_count ?? 0)} />
              <InfoCard icon={Download} label="الحد اليومي" value={String(u.daily_limit ?? 0)} />
              <InfoCard icon={Activity} label="إجمالي التحميلات" value={String(u.total_downloads ?? 0)} />
              <InfoCard icon={Smartphone} label="عدد الزيارات" value={String(u.visit_count ?? 0)} />
            </div>
            <p className="text-xs text-slate-500 mt-2 mb-1">آخر النشاطات</p>
            {u.downloads?.slice(0, 10).length > 0 ? (
              <div className="space-y-1">
                {u.downloads.slice(0, 10).map((d, i) => (
                  <div key={i} className="flex items-center gap-3 p-2 rounded-lg hover:bg-slate-800/30 transition-colors">
                    <div className="w-2 h-2 rounded-full bg-indigo-500 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-white truncate">{d.platform || 'تحميل'}</p>
                      <p className="text-xs text-slate-500">{d.downloaded_at ? new Date(d.downloaded_at).toLocaleString('ar-SA') : '—'}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500 text-center py-4">لا توجد نشاطات</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function InfoCard({ icon: Icon, label, value }) {
  return (
    <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50">
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-3.5 h-3.5 text-slate-500" />
        <span className="text-xs text-slate-500">{label}</span>
      </div>
      <p className="text-sm font-medium text-white">{value}</p>
    </div>
  );
}


