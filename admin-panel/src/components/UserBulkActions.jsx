import { useState } from 'react';
import { Ban, Trash2, Crown, Download, X } from 'lucide-react';

export default function UserBulkActions({
  selectedIds,
  onClear,
  onBulkBan,
  onBulkDelete,
  onBulkSetTier,
  onExport,
}) {
  const [showTierMenu, setShowTierMenu] = useState(false);
  const [busy, setBusy] = useState(false);
  const count = selectedIds.length;

  const doAction = async (fn) => {
    if (busy) return;
    setBusy(true);
    try {
      await fn();
    } finally {
      setBusy(false);
    }
  };

  if (count === 0) return null;

  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-indigo-600/10 border border-indigo-600/20 rounded-xl animate-in fade-in">
      <span className="text-sm text-indigo-300 font-medium ml-2">
        تم اختيار {count} مستخدم
      </span>

      <button
        onClick={() => doAction(() => onBulkBan(selectedIds))}
        disabled={busy}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 disabled:opacity-50 transition-colors"
      >
        <Ban className="w-3.5 h-3.5" /> حظر
      </button>

      <button
        onClick={() => doAction(() => onBulkDelete(selectedIds))}
        disabled={busy}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 disabled:opacity-50 transition-colors"
      >
        <Trash2 className="w-3.5 h-3.5" /> حذف
      </button>

      <div className="relative">
        <button
          onClick={() => setShowTierMenu(!showTierMenu)}
          disabled={busy}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 disabled:opacity-50 transition-colors"
        >
          <Crown className="w-3.5 h-3.5" /> تغيير المستوى
        </button>
        {showTierMenu && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setShowTierMenu(false)} />
            <div className="absolute bottom-full mb-2 right-0 z-50 bg-slate-800 border border-slate-700 rounded-xl shadow-xl p-2 min-w-[130px]">
              {['free', 'premium', 'vip', 'pro'].map((tier) => (
                <button
                  key={tier}
                  onClick={() => {
                    setShowTierMenu(false);
                    doAction(() => onBulkSetTier(selectedIds, tier));
                  }}
                  className="block w-full text-right px-3 py-2 rounded-lg text-xs font-medium text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
                >
                  {tier}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <button
        onClick={() => doAction(onExport)}
        disabled={busy}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50 transition-colors"
      >
        <Download className="w-3.5 h-3.5" /> تصدير CSV
      </button>

      <button
        onClick={onClear}
        disabled={busy}
        className="mr-auto p-1.5 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-white transition-colors"
        title="إلغاء التحديد"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
