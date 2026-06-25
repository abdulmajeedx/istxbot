import { useState, useEffect, useCallback, useRef } from 'react';
import { bot, stats } from '../api/client';
import { useToast } from '../components/Toast';
import ConfirmDialog from '../components/ConfirmDialog';
import CopyToClipboard from '../components/CopyToClipboard';
import EmptyState from '../components/EmptyState';
import { Spinner } from '../components/Skeleton';
import {
  RefreshCw, Trash2, AlertCircle, AlertTriangle, Info,
  Search, Download, Pause, Play, ScrollText,
} from 'lucide-react';

const levelIcons = {
  ERROR: AlertCircle, WARNING: AlertTriangle, INFO: Info, DEBUG: Info,
};
const levelColors = {
  ERROR: 'text-red-400 bg-red-500/10', WARNING: 'text-amber-400 bg-amber-500/10', INFO: 'text-sky-400 bg-sky-500/10', DEBUG: 'text-slate-400 bg-slate-500/10',
};

export default function LogsPage() {
  const { toast } = useToast();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [count, setCount] = useState(50);
  const [search, setSearch] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const intervalRef = useRef(null);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const level = filter === 'all' ? undefined : filter;
      const res = await bot.logs(count, level);
      setLogs(res.data?.logs || res.data || []);
    } catch (err) {
      toast.error('فشل تحميل السجلات');
    }
    setLoading(false);
  }, [filter, count, toast]);

  useEffect(() => { loadLogs(); }, [loadLogs]);

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(loadLogs, 10000);
      return () => clearInterval(intervalRef.current);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
  }, [autoRefresh, loadLogs]);

  const handleClear = async () => {
    setShowClearConfirm(false);
    try {
      await bot.deleteLogs();
      toast.success('تم مسح السجلات');
      loadLogs();
    } catch (err) {
      toast.error('فشل مسح السجلات');
    }
  };

  const handleExportCSV = async () => {
    try {
      const res = await stats.exportCSV();
      const blob = new Blob([res.data], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `logs_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('تم تصدير السجلات');
    } catch (err) {
      toast.error('فشل تصدير السجلات');
    }
  };

  const filteredLogs = search
    ? logs.filter((log) => {
        const text = log.message || log.text || '';
        return text.toLowerCase().includes(search.toLowerCase());
      })
    : logs;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">السجلات</h2>
          <p className="text-slate-500 text-sm mt-1">{logs.length} سجل</p>
        </div>
      </div>

      {/* Filters */}
      <div className="card space-y-3">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex gap-2">
            {['all', 'ERROR', 'WARNING', 'INFO'].map((l) => (
              <button key={l} onClick={() => setFilter(l)} className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${filter === l ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'}`}>
                {l === 'all' ? 'الكل' : l}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">عدد:</span>
            <select value={count} onChange={(e) => setCount(Number(e.target.value))} className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
              {[20, 50, 100, 200, 500].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <button onClick={() => setAutoRefresh(!autoRefresh)} className={`btn flex items-center gap-2 ${autoRefresh ? 'bg-indigo-600 text-white' : 'btn-ghost'}`}>
            {autoRefresh ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {autoRefresh ? 'إيقاف' : 'تلقائي'}
          </button>
          <div className="flex gap-2 mr-auto">
            <button onClick={loadLogs} className="btn btn-ghost flex items-center gap-2"><RefreshCw className="w-4 h-4" /> تحديث</button>
            <button onClick={handleExportCSV} className="btn btn-ghost flex items-center gap-2"><Download className="w-4 h-4" /> CSV</button>
            <button onClick={() => setShowClearConfirm(true)} className="btn btn-danger flex items-center gap-2"><Trash2 className="w-4 h-4" /> مسح</button>
          </div>
        </div>
        <div className="relative">
          <Search className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input className="input-field pl-4 pr-12" placeholder="بحث في السجلات..." value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>

      {/* Log Entries */}
      {loading ? (
        <div className="card flex items-center justify-center py-16">
          <Spinner size="md" label="جار تحميل السجلات..." />
        </div>
      ) : filteredLogs.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={ScrollText}
            title={search ? 'لا توجد نتائج' : 'لا توجد سجلات'}
            description={search ? `لا توجد سجلات تطابق "${search}"` : 'ستظهر السجلات هنا عند تشغيل البوت'}
          />
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <div className="font-mono text-xs max-h-[70vh] overflow-y-auto">
            {filteredLogs.map((log, i) => {
              const level = log.level || log.severity || 'INFO';
              const Icon = levelIcons[level] || Info;
              const colorClass = levelColors[level] || levelColors.INFO;
              return (
                <div key={i} className="flex items-start gap-3 px-4 py-2.5 hover:bg-slate-800/30 border-b border-slate-800/50 last:border-0 transition-colors group">
                  <span className={`p-1 rounded shrink-0 mt-0.5 ${colorClass}`}>
                    <Icon className="w-3 h-3" />
                  </span>
                  <span className="text-slate-500 shrink-0 w-20">{log.timestamp || log.time || ''}</span>
                  <span className="text-slate-400 flex-1 break-all leading-relaxed">{log.message || log.text || JSON.stringify(log)}</span>
                  <CopyToClipboard text={log.message || log.text || ''} iconOnly className="opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              );
            })}
          </div>
        </div>
      )}

      <ConfirmDialog
        open={showClearConfirm}
        title="مسح السجلات"
        message="هل أنت متأكد من مسح جميع السجلات؟ لا يمكن التراجع عن هذا الإجراء."
        confirmText="نعم، امسح الكل"
        cancelText="إلغاء"
        variant="danger"
        onConfirm={handleClear}
        onCancel={() => setShowClearConfirm(false)}
      />
    </div>
  );
}
