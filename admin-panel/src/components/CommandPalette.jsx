import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, LayoutDashboard, Users, BarChart3, Settings,
  ScrollText, Radio, Database, Server, Play, Square, RotateCw,

} from 'lucide-react';

// Actions + pages that can be searched/navigated to
const COMMANDS = [
  // Pages
  { id: 'dashboard', label: 'الرئيسية', icon: LayoutDashboard, action: 'navigate', to: '/', shortcut: 'g d', keywords: ['home', 'dashboard', 'رئيسية'] },
  { id: 'users', label: 'المستخدمين', icon: Users, action: 'navigate', to: '/users', shortcut: 'g u', keywords: ['users', 'مستخدمين', 'عملاء'] },
  { id: 'analytics', label: 'التحليلات', icon: BarChart3, action: 'navigate', to: '/analytics', shortcut: 'g a', keywords: ['analytics', 'تحليلات', 'احصائيات'] },
  { id: 'settings', label: 'الإعدادات', icon: Settings, action: 'navigate', to: '/settings', shortcut: 'g s', keywords: ['settings', 'اعدادات', 'خيارات'] },
  { id: 'logs', label: 'السجلات', icon: ScrollText, action: 'navigate', to: '/logs', shortcut: 'g l', keywords: ['logs', 'سجلات', 'سجل'] },
  { id: 'broadcast', label: 'رسالة جماعية', icon: Radio, action: 'navigate', to: '/broadcast', keywords: ['broadcast', 'اذاعة', 'جماعية'] },
  { id: 'database', label: 'قاعدة البيانات', icon: Database, action: 'navigate', to: '/database', keywords: ['database', 'قاعدة'] },
  { id: 'system', label: 'النظام', icon: Server, action: 'navigate', to: '/system', keywords: ['system', 'نظام', 'سيرفر'] },
  // Actions
  { id: 'bot-start', label: 'تشغيل البوت', icon: Play, action: 'custom', keywords: ['start', 'تشغيل'] },
  { id: 'bot-stop', label: 'إيقاف البوت', icon: Square, action: 'custom', keywords: ['stop', 'ايقاف'] },
  { id: 'bot-restart', label: 'إعادة تشغيل البوت', icon: RotateCw, action: 'custom', keywords: ['restart', 'اعادة'] },
  { id: 'backup', label: 'نسخ احتياطي', icon: Download, action: 'custom', keywords: ['backup', 'نسخ'] },
];

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  // Open with Ctrl+K / Cmd+K
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Focus input on open
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery('');
      setSelectedIndex(0);
    }
  }, [open]);

  // Filter commands
  const filtered = query
    ? COMMANDS.filter(
        (c) =>
          c.label.includes(query) ||
          c.keywords?.some((k) => k.includes(query.toLowerCase()))
      )
    : COMMANDS;

  // Reset selection when filtered list changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleSelect = useCallback(
    (cmd) => {
      if (cmd.action === 'navigate') {
        navigate(cmd.to);
        setOpen(false);
      } else if (cmd.action === 'custom') {
        // Custom actions will be handled by the parent via events
        window.dispatchEvent(new CustomEvent('command-palette-action', { detail: cmd.id }));
        setOpen(false);
      }
    },
    [navigate]
  );

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.min(prev + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[selectedIndex]) handleSelect(filtered[selectedIndex]);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-start justify-center pt-[15vh]"
      onClick={() => setOpen(false)}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      {/* Palette */}
      <div
        className="relative w-full max-w-lg bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 mx-4"
        onClick={(e) => e.stopPropagation()}
        style={{
          boxShadow: '0 25px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(99,102,241,0.1)',
        }}
      >
        {/* Search Input */}
        <div className="flex items-center gap-3 px-4 border-b border-slate-800">
          <Search className="w-5 h-5 text-slate-500 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            className="flex-1 bg-transparent py-4 text-white text-sm placeholder-slate-500 outline-none"
            placeholder="ابحث عن صفحة أو إجراء..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            dir="rtl"
          />
          <kbd className="hidden sm:inline-flex items-center gap-0.5 px-2 py-0.5 rounded-md bg-slate-800 border border-slate-700 text-xs text-slate-500 font-sans">
            Esc
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-72 overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <div className="text-center py-8 text-sm text-slate-500">
              لا توجد نتائج لـ "{query}"
            </div>
          ) : (
            filtered.map((cmd, i) => {
              const Icon = cmd.icon;
              return (
                <button
                  key={cmd.id}
                  onClick={() => handleSelect(cmd)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all group ${
                    i === selectedIndex
                      ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-600/30'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                  }`}
                  onMouseEnter={() => setSelectedIndex(i)}
                >
                  <Icon className="w-5 h-5 shrink-0" />
                  <span className="flex-1 text-right">{cmd.label}</span>
                  {cmd.shortcut && (
                    <span className="text-xs text-slate-600 font-mono hidden sm:inline">
                      {cmd.shortcut}
                    </span>
                  )}
                  {i === selectedIndex && (
                    <ArrowRight className="w-3 h-3 text-indigo-400 hidden sm:block" />
                  )}
                </button>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-4 px-4 py-2.5 border-t border-slate-800 text-xs text-slate-600">
          <span>↑↓ تنقل</span>
          <span>↵ اختيار</span>
          <span>Esc إغلاق</span>
        </div>
      </div>
    </div>
  );
}

