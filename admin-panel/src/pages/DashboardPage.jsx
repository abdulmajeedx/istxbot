import { useState, useEffect, useCallback } from 'react';
import { bot, stats, system } from '../api/client';
import { useToast } from '../components/Toast';
import AnimatedCounter from '../components/AnimatedCounter';
import { DashboardSkeleton } from '../components/Skeleton';
import {
  Users, Download, Eye, TrendingUp,
  Play, Square, RotateCw, Activity,
  Server, Cpu, HardDrive, Clock
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

function StatCard({ icon: Icon, label, value, sub, color = 'indigo' }) {
  const colors = {
    indigo: 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400',
    emerald: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400',
    amber: 'bg-amber-500/10 border-amber-500/20 text-amber-400',
    rose: 'bg-rose-500/10 border-rose-500/20 text-rose-400',
    sky: 'bg-sky-500/10 border-sky-500/20 text-sky-400',
  };

  const numValue = typeof value === 'string' ? parseFloat(value) : value;

  return (
    <div className="card flex items-start gap-4 group transition-all duration-300 hover:border-indigo-500/20 hover:shadow-lg hover:shadow-indigo-500/5">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center border transition-transform duration-300 group-hover:scale-110 ${colors[color]}`}>
        <Icon className="w-6 h-6" />
      </div>
      <div className="min-w-0">
        <p className="text-2xl font-bold text-white tabular-nums">
          {typeof numValue === 'number' && !isNaN(numValue) ? (
            <AnimatedCounter value={numValue} duration={600} />
          ) : (
            value
          )}
        </p>
        <p className="text-sm text-slate-400">{label}</p>
        {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { toast } = useToast();
  const [botStatus, setBotStatus] = useState(null);
  const [botStats, setBotStats] = useState(null);
  const [sysInfo, setSysInfo] = useState(null);

  const [actionLoading, setActionLoading] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [statusRes, statsRes, sysRes] = await Promise.all([
        bot.status(),
        stats.overview(),
        system.info().catch(() => ({ data: null })),
      ]);
      setBotStatus(statusRes.data);
      setBotStats(statsRes.data);
      setSysInfo(sysRes.data);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  const botAction = async (action) => {
    setActionLoading(true);
    try {
      if (action === 'start') {
        await bot.start();
        toast.success('تم تشغيل البوت');
      } else if (action === 'stop') {
        await bot.stop();
        toast.success('تم إيقاف البوت');
      } else if (action === 'restart') {
        await bot.restart();
        toast.success('جاري إعادة تشغيل البوت...');
      }
      setTimeout(loadData, 2000);
    } catch (err) {
      toast.error(`فشل ${action === 'start' ? 'التشغيل' : action === 'stop' ? 'الإيقاف' : 'إعادة التشغيل'}`);
    }
    setActionLoading(false);
  };

  if (loading) return <DashboardSkeleton />;

  const isRunning = botStatus?.active === 'active';
  const platformData = botStats?.platforms
    ? Object.entries(botStats.platforms).map(([k, v]) => ({ name: k, تحميلات: v || 0 }))
    : [];

  const formatUptime = (seconds) => {
    if (!seconds) return 'N/A';
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const parts = [];
    if (d > 0) parts.push(`${d}يوم`);
    if (h > 0) parts.push(`${h}س`);
    if (m > 0) parts.push(`${m}د`);
    return parts.join(' ') || '<1د';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white">لوحة التحكم</h2>
          <p className="text-slate-500 text-sm mt-1">مرحباً بك في لوحة تحكم ساحِب</p>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full ${isRunning ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
          <span className={`text-sm font-medium ${isRunning ? 'text-emerald-400' : 'text-red-400'}`}>
            {isRunning ? 'شغال' : 'متوقف'}
          </span>
        </div>
      </div>

      {/* Bot Controls */}
      <div className="card">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-indigo-400" />
            <span className="text-sm text-slate-400">التحكم:</span>
          </div>
          <button onClick={() => botAction('start')} disabled={isRunning || actionLoading} className="btn btn-success">
            <Play className="w-4 h-4" /> تشغيل
          </button>
          <button onClick={() => botAction('stop')} disabled={!isRunning || actionLoading} className="btn btn-danger">
            <Square className="w-4 h-4" /> إيقاف
          </button>
          <button onClick={() => botAction('restart')} disabled={actionLoading} className="btn btn-ghost">
            <RotateCw className={`w-4 h-4 ${actionLoading ? 'animate-spin' : ''}`} /> إعادة
          </button>
          {botStatus?.pid && (
            <span className="text-xs text-slate-500 mr-auto">
              PID: {botStatus.pid} | RAM: {(parseInt(botStatus.memory || 0) / 1024 / 1024).toFixed(1)} MB
            </span>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Users} label="المستخدمين" value={botStats?.total_users || 0} sub={`نشط: ${botStats?.active_users || 0}`} color="indigo" />
        <StatCard icon={Download} label="التحميلات" value={botStats?.total_downloads || 0} sub={`اليوم: ${botStats?.today_downloads || 0}`} color="emerald" />
        <StatCard icon={Eye} label="الزوار" value={botStats?.total_visitors || 0} color="amber" />
        <StatCard icon={TrendingUp} label="نسبة النجاح" value={`${botStats?.success_rate || 0}%`} color="sky" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Platform Chart */}
        {platformData.length > 0 && (
          <div className="card">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-indigo-400" />
              التحميلات حسب المنصة
            </h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={platformData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis type="number" stroke="#64748b" />
                  <YAxis dataKey="name" type="category" stroke="#64748b" width={80} />
                  <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '12px' }} />
                  <Bar dataKey="تحميلات" fill="#6366f1" radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Server Info */}
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Server className="w-5 h-5 text-indigo-400" />
            معلومات السيرفر
          </h3>
          <div className="space-y-4">
            {[
              { icon: Cpu, label: 'المعالج', value: sysInfo?.cpu_usage, color: 'bg-indigo-500' },
              { icon: HardDrive, label: 'الذاكرة', value: sysInfo?.memory_usage, color: 'bg-emerald-500' },
            ].map(({ icon: Icon, label, value, color }) => (
              <div key={label} className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm">
                  <Icon className="w-4 h-4 text-slate-500" />
                  <span className="text-slate-400">{label}</span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-24 bg-slate-700 rounded-full h-2 overflow-hidden">
                    <div className={`${color} h-2 rounded-full transition-all duration-500`} style={{ width: `${value || 0}%` }} />
                  </div>
                  <span className="text-sm text-white font-medium w-10 text-left">{value || '-'}%</span>
                </div>
              </div>
            ))}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                <Clock className="w-4 h-4 text-slate-500" />
                <span className="text-slate-400">وقت التشغيل</span>
              </div>
              <span className="text-sm text-white font-medium">{formatUptime(sysInfo?.uptime_seconds)}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                <HardDrive className="w-4 h-4 text-slate-500" />
                <span className="text-slate-400">القرص</span>
              </div>
              <span className="text-sm text-white font-medium">{sysInfo?.disk_usage || '-'}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

