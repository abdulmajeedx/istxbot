import { AlertTriangle, X } from 'lucide-react';

export default function ConfirmDialog({
  open,
  title = 'تأكيد',
  message = 'هل أنت متأكد؟',
  confirmText = 'تأكيد',
  cancelText = 'إلغاء',
  variant = 'danger', // danger | warning | info
  loading = false,
  onConfirm,
  onCancel,
}) {
  if (!open) return null;

  const variantStyles = {
    danger: {
      icon: 'text-red-400 bg-red-500/10 border-red-500/20',
      btn: 'btn-danger',
    },
    warning: {
      icon: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
      btn: 'bg-amber-600/20 hover:bg-amber-600/40 text-amber-400 border border-amber-600/30 px-4 py-2 rounded-xl font-medium transition-all duration-200 text-sm',
    },
    info: {
      icon: 'text-sky-400 bg-sky-500/10 border-sky-500/20',
      btn: 'btn-primary',
    },
  };

  const styles = variantStyles[variant] || variantStyles.danger;

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] p-4"
      onClick={onCancel}
    >
      <div
        className="card w-full max-w-md space-y-4 animate-in zoom-in-95"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center border ${styles.icon}`}>
              <AlertTriangle className="w-5 h-5" />
            </div>
            <h3 className="text-lg font-semibold text-white">{title}</h3>
          </div>
          <button
            onClick={onCancel}
            className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Message */}
        <p className="text-sm text-slate-400 leading-relaxed">{message}</p>

        {/* Actions */}
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            disabled={loading}
            className="btn btn-ghost"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`btn ${styles.btn} min-w-[80px]`}
          >
            {loading ? 'جاري...' : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
