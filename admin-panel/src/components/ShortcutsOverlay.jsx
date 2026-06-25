import { useState, useEffect } from 'react';
import { X, Keyboard } from 'lucide-react';

const SHORTCUT_GROUPS = [
  {
    title: 'عام',
    shortcuts: [
      { keys: ['Ctrl', 'K'], desc: 'فتح لوحة الأوامر' },
      { keys: ['?'], desc: 'إظهار الاختصارات' },
      { keys: ['Esc'], desc: 'إغلاق أي نافذة' },
    ],
  },
  {
    title: 'التنقل',
    shortcuts: [
      { keys: ['G', 'D'], desc: 'الذهاب للرئيسية' },
      { keys: ['G', 'U'], desc: 'الذهاب للمستخدمين' },
      { keys: ['G', 'A'], desc: 'الذهاب للتحليلات' },
      { keys: ['G', 'S'], desc: 'الذهاب للإعدادات' },
      { keys: ['G', 'L'], desc: 'الذهاب للسجلات' },
    ],
  },
  {
    title: 'الإجراءات',
    shortcuts: [
      { keys: ['Ctrl', 'B'], desc: 'نسخ احتياطي لقاعدة البيانات' },
      { keys: ['Ctrl', 'R'], desc: 'تحديث الصفحة الحالية' },
    ],
  },
];

export default function ShortcutsOverlay() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handler = (e) => {
      // Don't trigger when typing in inputs
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) {
        return;
      }

      if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center"
      onClick={() => setOpen(false)}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      {/* Modal */}
      <div
        className="relative w-full max-w-lg bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl animate-in zoom-in-95 mx-4 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        style={{ boxShadow: '0 25px 60px rgba(0,0,0,0.5)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600/10 border border-indigo-600/20 flex items-center justify-center">
              <Keyboard className="w-5 h-5 text-indigo-400" />
            </div>
            <h2 className="text-lg font-semibold text-white">اختصارات لوحة المفاتيح</h2>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="p-2 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Shortcuts */}
        <div className="p-5 space-y-6">
          {SHORTCUT_GROUPS.map((group) => (
            <div key={group.title}>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                {group.title}
              </h3>
              <div className="space-y-2">
                {group.shortcuts.map((s) => (
                  <div
                    key={s.desc}
                    className="flex items-center justify-between py-2 px-3 rounded-xl hover:bg-slate-800/30 transition-colors"
                  >
                    <span className="text-sm text-slate-300">{s.desc}</span>
                    <div className="flex items-center gap-1">
                      {s.keys.map((key, i) => (
                        <span key={i}>
                          <kbd className="px-2 py-0.5 rounded-md bg-slate-800 border border-slate-700 text-xs text-slate-400 font-mono">
                            {key}
                          </kbd>
                          {i < s.keys.length - 1 && (
                            <span className="text-slate-600 mx-0.5">+</span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-800 text-center">
          <p className="text-xs text-slate-600">
            اضغط <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400 font-mono">?</kbd> في أي وقت لإظهار هذه القائمة
          </p>
        </div>
      </div>
    </div>
  );
}
