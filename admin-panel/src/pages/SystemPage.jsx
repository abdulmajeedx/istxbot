import { useState, useEffect, useCallback } from 'react';
import { system, bot } from '../api/client';
import { useToast } from '../components/Toast';
import ConfirmDialog from '../components/ConfirmDialog';
import {
  Server, Cpu, HardDrive, Clock, RefreshCw,
  Activity, Power, Terminal, Loader2, Wifi, WifiOff
} from 'lucide-react';

export default function SystemPage() {
  const { toast } = useToast();
  const [sysInfo, setSysInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [restarting, setRestarting] = useState(false);


  const loadInfo = useCallback(async () => {
    setLoading(true);
    try {
      const [sysRes, botRes] = await Promise.all([
        system.info(),
        bot.status(),
      ]);
      setSysInfo({
        ...sysRes.data,
        bot: botRes.data,
      });
    } catch (err) {
      toast.error('فشل تحميل معلومات النظام');
    }
    setLoading(false);
  }, [toast]);

  useEffect(() => { loadInfo(); }, [loadInfo]);

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(loadInfo, 30000);
    return () => clearInterval(interval);
  }, [loadInfo]);

  const handleRestart = async () => {
    setShowRestartConfirm(false);
    setRestarting(true);
    try {
      await system.restart();
      toast.success('جاري إعادة تشغيل السيرفر...');
      setTimeout(loadInfo, 5000);
    } catch (err) {
      toast.error('فشل إعادة تشغيل السيرفر');
    }
    setRestarting(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
      </div>
    );
  }

  const formatUptime = (seconds) => {
    if (!seconds) return 'N/A';
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const parts = [];
    if (d > 0) parts.push(`${d} يوم`);
    if (h > 0) parts.push(`${h} ساعة`);
    if (m > 0) parts.push(`${m} دقيقة`);
    return parts.join(' ') || 'أقل من دقيقة';
  };

  const botRunning = sysInfo?.bot?.active === 'active';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">النظام</h2>
          <p className="text-slate-500 text-sm mt-1">معلومات وأدوات إدارة السيرفر</p>
        </div>
        <button onClick={loadInfo} className="btn btn-ghost flex items-center gap-2">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          تحديث
        </button>
      </div>

      {/* System Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xl font-bold text-white">{sysInfo?.cpu_usage || '-'}%</p>
            <p className="text-xs text-slate-500">المعالج</p>
          </div>
        </div>
        <div className="card flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <HardDrive className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xl font-bold text-white">{sysInfo?.memory_usage || '-'}%</p>
            <p className="text-xs text-slate-500">الذاكرة</p>
          </div>
        </div>
        <div className="card flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <HardDrive className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xl font-bold text-white">{sysInfo?.disk_usage || '-'}%</p>
            <p className="text-xs text-slate-500">القرص</p>
          </div>
        </div>
        <div className="card flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <Clock className="w-5 h-5" />
          </div>
          <div>
            <p className="text-sm font-bold text-white">{formatUptime(sysInfo?.uptime_seconds)}</p>
            <p className="text-xs text-slate-500">وقت التشغيل</p>
          </div>
        </div>
      </div>

      {/* Services Status */}
      <div className="card space-y-4">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <Activity className="w-5 h-5 text-indigo-400" />
          حالة الخدمات
        </h3>
        <div className="space-y-3">
          {/* Bot Service */}
          <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-xl">
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${botRunning ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
                {botRunning ? (
                  <Activity className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Power className="w-4 h-4 text-red-400" />
                )}
              </div>
              <div>
                <p className="font-medium text-white">بوت تيليجرام (@istxbot)</p>
                <p className="text-xs text-slate-500">
                  {botRunning
                    ? `شغال — PID: ${sysInfo?.bot?.pid || '?'} | RAM: ${sysInfo?.bot?.memory ? (parseInt(sysInfo.bot.memory) / 1024 / 1024).toFixed(1) : '?'} MB`
                    : 'متوقف'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {botRunning ? (
                <Wifi className="w-4 h-4 text-emerald-400" />
              ) : (
                <WifiOff className="w-4 h-4 text-red-400" />
              )}
              <span className={`text-sm font-medium ${botRunning ? 'text-emerald-400' : 'text-red-400'}`}>
                {botRunning ? 'نشط' : 'متوقف'}
              </span>
            </div>
          </div>

          {/* Web Service */}
          <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-xl">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-sky-500/10 flex items-center justify-center">
                <Server className="w-4 h-4 text-sky-400" />
              </div>
              <div>
                <p className="font-medium text-white">منصة الويب</p>
                <p className="text-xs text-slate-500">المنفذ 8080 — inspiredownloader.com</p>
              </div>
            </div>
            <span className="text-sm font-medium text-sky-400 flex items-center gap-2">
              <Wifi className="w-4 h-4" />
              نشط
            </span>
          </div>

          {/* Monitor Service */}
          <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-xl">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center">
                <Terminal className="w-4 h-4 text-purple-400" />
              </div>
              <div>
                <p className="font-medium text-white">لوحة المراقبة</p>
                <p className="text-xs text-slate-500">المنفذ 8090</p>
              </div>
            </div>
            <span className="text-sm font-medium text-purple-400 flex items-center gap-2">
              <Wifi className="w-4 h-4" />
              نشط
            </span>
          </div>
        </div>
      </div>

      {/* Server Actions */}
      <div className="card space-y-4">
        <h3 className="text-lg font-semibold text-white">إجراءات السيرفر</h3>

        <div className="space-y-3">
          <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-xl">
            <div>
              <p className="font-medium text-white">إعادة تشغيل البوت</p>
              <p className="text-xs text-slate-500">إعادة تشغيل خدمة البوت (قد تستغرق ثواني)</p>
            </div>
            <button
              onClick={() => setShowRestartConfirm(true)}
              disabled={restarting}
              className="btn btn-danger flex items-center gap-2"
            >
              {restarting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  جاري...
                </>
              ) : (
                <>
                  <Power className="w-4 h-4" />
                  إعادة تشغيل
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* System Details */}
      {sysInfo?.details && (
        <div className="card space-y-4">
          <h3 className="text-lg font-semibold text-white">تفاصيل النظام</h3>
          <pre className="bg-slate-900 border border-slate-700 rounded-xl p-4 text-xs text-slate-300 overflow-auto max-h-64" dir="ltr">
            {JSON.stringify(sysInfo.details, null, 2)}
          </pre>
        </div>
      )}

      {/* Confirm Restart */}
      <ConfirmDialog
        open={showRestartConfirm}
        title="إعادة تشغيل البوت"
        message="هل أنت متأكد من إعادة تشغيل البوت؟ قد يتأثر المستخدمون النشطون مؤقتاً."
        confirmText="نعم، أعد التشغيل"
        cancelText="إلغاء"
        variant="warning"
        loading={restarting}
        onConfirm={handleRestart}
        onCancel={() => setShowRestartConfirm(false)}
      />
    </div>
  );
}

