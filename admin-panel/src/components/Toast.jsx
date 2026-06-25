import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react';

const ToastContext = createContext(null);

const ICONS = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const COLORS = {
  success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
  error: 'border-red-500/30 bg-red-500/10 text-red-400',
  warning: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
  info: 'border-sky-500/30 bg-sky-500/10 text-sky-400',
};

let toastId = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, message, type, duration }]);
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Convenience methods
  const toast = {
    success: (msg, dur) => addToast(msg, 'success', dur),
    error: (msg, dur) => addToast(msg, 'error', dur),
    warning: (msg, dur) => addToast(msg, 'warning', dur),
    info: (msg, dur) => addToast(msg, 'info', dur),
  };

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast, toast }}>
      {children}
      {/* Toast Container — positioned top-left for RTL */}
      <div
        className="fixed top-4 left-4 z-[9999] flex flex-col gap-2 pointer-events-none"
        style={{ maxWidth: 420 }}
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} {...t} onRemove={removeToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ id, message, type, duration, onRemove }) {
  const [exiting, setExiting] = useState(false);
  const Icon = ICONS[type] || ICONS.info;

  useEffect(() => {
    if (!duration) return;
    const timer = setTimeout(() => setExiting(true), duration - 300);
    const removeTimer = setTimeout(() => onRemove(id), duration);
    return () => {
      clearTimeout(timer);
      clearTimeout(removeTimer);
    };
  }, [id, duration, onRemove]);

  return (
    <div
      className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl border backdrop-blur-xl shadow-2xl transition-all duration-300 ${
        COLORS[type] || COLORS.info
      } ${exiting ? 'opacity-0 translate-x-4' : 'opacity-100 translate-x-0'}`}
      style={{
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      }}
    >
      <Icon className="w-5 h-5 shrink-0 mt-0.5" />
      <p className="text-sm flex-1">{message}</p>
      <button
        onClick={() => onRemove(id)}
        className="shrink-0 p-0.5 rounded-lg hover:bg-white/10 transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be inside ToastProvider');
  return ctx;
}

export default ToastContext;
