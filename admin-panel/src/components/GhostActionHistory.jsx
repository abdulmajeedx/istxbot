import { useState, useEffect, useCallback } from 'react';
import {
  X, Ghost, Search, Clock, ArrowUpRight, ArrowDownRight, Minus, History, Calendar,
} from 'lucide-react';
import { admin } from '../api/client';
import { useToast } from './Toast';
import EmptyState from './EmptyState';
import TierBadge from './TierBadge';

/**
 * مكون سجل عمليات الشبح (Ghost Action History)
 *
 * يعرض مودال يحتوي على جدول بآخر تغييرات المستويات التي تمت في وضع الشبح
 * Props:
 *   open     - boolean: هل المودال مفتوح
 *   onClose  - () => void: دالة إغلاق المودال
 */
export default function GhostActionHistory({ open, onClose }) {
  const { toast } = useToast();
  const [actions, setActions] = useState([]);

  const [searchId, setSearchId] = useState('');
  const [filterId, setFilterId] = useState('');

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filterId) params.user_id = parseInt(filterId, 10);
      params.limit = 100;
      const { data } = await admin.ghostGetHistory(params);
      setActions(data?.actions || []);
    } catch {
      toast.error('فشل تحميل سجل التغييرات');
      setActions([]);
    }
    setLoading(false);
  }, [filterId, toast]);

  useEffect(() => {
    if (open) loadHistory();
  }, [open, loadHistory]);

  const handleSearch = () => {
    const id = searchId.trim();
    setFilterId(id);
  };

  const handleClearSearch = () => {
    setSearchId('');
    setFilterId('');
  };

  /** تحديد اتجاه التغيير للعرض */
  const getDirectionBadge = (oldTier, newTier) => {
    const order = ['free', 'premium', 'vip', 'pro'];
    const oldIdx = order.indexOf((oldTier || 'free').toLowerCase());
    const newIdx = order.indexOf((newTier || 'free').toLowerCase());

    if (newIdx > oldIdx) {
      return (
        <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
          <ArrowUpRight className="w-3 h-3" />
          ترقية
        </span>
      );
    } else if (newIdx < oldIdx) {
      return (
        <span className="inline-flex items-center gap-1 text-xs text-red-400">
          <ArrowDownRight className="w-3 h-3" />
          إنزال
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-xs text-slate-400">
        <Minus className="w-3 h-3" />
        تعديل
      </span>
    );
  };

  /** تنسيق المدة */
  const formatDuration = (seconds) => {
    if (!seconds) return 'دائمة';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    if (days > 0) return `${days} يوم`;
    if (hours > 0) return `${hours} ساعة`;
    return `${Math.round(seconds / 60)} دقيقة`;
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[110] p-4"
      onClick={onClose}
    >
      <div
        className="card w-full max-w-3xl max-h-[85vh] flex flex-col animate-in zoom-in-95"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ═══ الرأس ═══ */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center border bg-indigo-500/10 border-indigo-500/20 text-indigo-400">
              <History className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">سجل عمليات الشبح</h3>
              <p className="text-xs text-slate-500">سجل تدقيق تغييرات المستويات الصامتة</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* ═══ شريط البحث ═══ */}
        <div className="flex items-center gap-2 py-3 border-b border-slate-800">
          <div className="relative flex-1">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="number"
              className="input-field pr-10 text-sm"
              placeholder="بحث بمعرف المستخدم (User ID)..."
              value={searchId}
              onChange={(e) => setSearchId(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              dir="ltr"
            />
          </div>
          <button
            onClick={handleSearch}
            className="btn btn-primary text-xs px-4 py-2"
          >
            بحث
          </button>
          {filterId && (
            <button
              onClick={handleClearSearch}
              className="btn btn-ghost text-xs px-3 py-2"
            >
              مسح
            </button>
          )}
        </div>

        {/* ═══ المحتوى ═══ */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {loading ? (
            /* ── حالة التحميل (Skeleton) ── */
            <div className="space-y-3 p-4 animate-pulse">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 p-3 rounded-xl bg-slate-800/30">
                  <div className="w-16 h-4 skeleton rounded" />
                  <div className="w-24 h-4 skeleton rounded" />
                  <div className="w-20 h-4 skeleton rounded" />
                  <div className="flex-1 h-4 skeleton rounded" />
                  <div className="w-24 h-4 skeleton rounded" />
                </div>
              ))}
            </div>
          ) : actions.length === 0 ? (
            /* ── حالة الفراغ ── */
            <div className="p-8">
              <EmptyState
                icon={Ghost}
                title="لا توجد سجلات"
                description={filterId ? 'لا توجد عمليات شبح لهذا المستخدم' : 'لم تُسجل أي عملية تعديل في وضع الشبح بعد'}
              />
            </div>
          ) : (
            /* ── جدول السجلات ── */
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-slate-900/95 backdrop-blur-sm">
                  <tr className="text-slate-400 text-right text-xs">
                    <th className="p-3 font-medium">
                      <span className="flex items-center gap-1.5">
                        <Calendar className="w-3 h-3" /> التاريخ
                      </span>
                    </th>
                    <th className="p-3 font-medium">المستخدم</th>
                    <th className="p-3 font-medium">من ← إلى</th>
                    <th className="p-3 font-medium">الاتجاه</th>
                    <th className="p-3 font-medium">
                      <span className="flex items-center gap-1.5">
                        <Clock className="w-3 h-3" /> المدة
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {actions.map((action) => (
                    <tr key={action.id} className="hover:bg-slate-800/20 transition-colors">
                      <td className="p-3 text-xs text-slate-400 whitespace-nowrap" dir="ltr">
                        {action.created_at
                          ? new Date(action.created_at).toLocaleString('ar-SA', {
                              day: 'numeric',
                              month: 'short',
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : '—'}
                      </td>
                      <td className="p-3 text-xs font-mono text-white" dir="ltr">
                        #{action.user_id}
                      </td>
                      <td className="p-3">
                        <div className="flex items-center gap-1.5 text-xs">
                          <TierBadge tier={action.old_tier || 'free'} />
                          <span className="text-slate-600">→</span>
                          <TierBadge tier={action.new_tier || 'free'} />
                        </div>
                      </td>
                      <td className="p-3">
                        {getDirectionBadge(action.old_tier, action.new_tier)}
                      </td>
                      <td className="p-3 text-xs text-slate-400">
                        {formatDuration(action.expires_in)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ═══ الذيل ═══ */}
        <div className="flex items-center justify-between pt-3 border-t border-slate-800">
          <span className="text-xs text-slate-500">
            {actions.length} عملية مسجلة
          </span>
          <button
            onClick={onClose}
            className="btn btn-ghost text-xs px-4 py-2"
          >
            إغلاق
          </button>
        </div>
      </div>
    </div>
  );
}

