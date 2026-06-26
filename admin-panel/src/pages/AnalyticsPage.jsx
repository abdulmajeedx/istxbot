import { useState, useEffect, useCallback } from 'react';
import { stats } from '../api/client';
import { useToast } from '../components/Toast';
import AnimatedCounter from '../components/AnimatedCounter';
import { StatsGridSkeleton, ChartSkeleton } from '../components/Skeleton';
import {
  BarChart3, TrendingUp, Download, Users, Calendar, FileDown,
} from 'lucide-react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from 'recharts';

const COLORS = ['#6366f1', '#a855f7', '#ec4899', '#f59e0b', '#10b981', '#06b6d4', '#f43f5e', '#84cc16'];

function StatMini({ icon: Icon, label, value, color }) {
  const colorMap = {
    indigo: 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400',
    emerald: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400',
    amber: 'bg-amber-500/10 border-amber-500/20 text-amber-400',
    rose: 'bg-rose-500/10 border-rose-500/20 text-rose-400',
  };
  const numValue = typeof value === 'string' ? parseFloat(value) : value;

  return (
    <div className="flex items-center gap-3 p-4 bg-slate-800/30 rounded-xl group transition-all duration-300 hover:bg-slate-800/50">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center border transition-transform duration-300 group-hover:scale-110 ${colorMap[color]}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-xl font-bold text-white tabular-nums">
          {typeof numValue === 'number' && !isNaN(numValue) ? (
            <AnimatedCounter value={numValue} duration={500} />
          ) : (
            value
          )}
        </p>
        <p className="text-xs text-slate-500">{label}</p>
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const { toast } = useToast();
  const [data, setData] = useState(null);


  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [aRes, cRes] = await Promise.all([stats.analytics(), stats.charts()]);
      setData({ analytics: aRes.data, charts: cRes.data });
    } catch (err) {
      toast.error('فشل تحميل التحليلات');
    }
    setLoading(false);
  }, [toast]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleExport = async () => {
    try {
      const res = await stats.exportCSV();
      const blob = new Blob([res.data], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analytics_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('تم تصدير التقرير');
    } catch (err) {
      toast.error('فشل تصدير التقرير');
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <div className="skeleton h-8 w-48 rounded-lg" />
            <div className="skeleton h-4 w-32 rounded-lg" />
          </div>
        </div>
        <StatsGridSkeleton />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ChartSkeleton />
          <ChartSkeleton />
        </div>
      </div>
    );
  }

  const analytics = data?.analytics || {};
  const charts = data?.charts || {};
  const pieData = analytics?.platforms
    ? Object.entries(analytics.platforms).filter(([, v]) => v > 0).map(([k, v]) => ({ name: k, value: v }))
    : [];
  const trendData = charts?.daily_trend || analytics?.daily_trend || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white">التحليلات</h2>
          <p className="text-slate-500 text-sm mt-1">إحصائيات وتقارير مفصلة</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-1 bg-slate-800 rounded-xl p-1">
            {[
              { key: '7d', label: '7 أيام' },
              { key: '30d', label: '30 يوم' },
              { key: '90d', label: '90 يوم' },
            ].map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setDateRange(key)}
                className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  dateRange === key ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <button onClick={handleExport} className="btn btn-ghost flex items-center gap-2">
            <FileDown className="w-4 h-4" /> تصدير
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatMini icon={Download} label="تحميلات اليوم" value={analytics?.today_downloads || 0} color="indigo" />
        <StatMini icon={Users} label="مستخدمين جدد" value={analytics?.new_users || 0} color="emerald" />
        <StatMini icon={TrendingUp} label="نسبة النجاح" value={`${analytics?.success_rate || 0}%`} color="amber" />
        <StatMini icon={BarChart3} label="متوسط يومي" value={analytics?.daily_avg || 0} color="rose" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Downloads Trend */}
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-indigo-400" />
            اتجاه التحميلات
          </h3>
          <div className="h-72">
            {trendData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
                  <YAxis stroke="#64748b" fontSize={12} />
                  <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '12px' }} labelStyle={{ color: '#e2e8f0' }} />
                  <Line type="monotone" dataKey="downloads" stroke="#6366f1" strokeWidth={2} dot={{ fill: '#6366f1', r: 3 }} activeDot={{ r: 6, fill: '#818cf8' }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-slate-500">لا توجد بيانات كافية</div>
            )}
          </div>
        </div>

        {/* Platform Distribution */}
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-indigo-400" />
            توزيع المنصات
          </h3>
          <div className="h-72">
            {pieData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={2} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                    {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '12px' }} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-slate-500">لا توجد بيانات</div>
            )}
          </div>
        </div>
      </div>

      {/* Hourly Distribution */}
      {charts?.hourly_distribution?.length > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Calendar className="w-5 h-5 text-indigo-400" />
            التوزيع حسب الساعة
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={charts.hourly_distribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="hour" stroke="#64748b" fontSize={12} />
                <YAxis stroke="#64748b" fontSize={12} />
                <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '12px' }} />
                <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Top Users */}
      {analytics?.top_users?.length > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">أكثر المستخدمين نشاطاً</h3>
          <div className="space-y-2">
            {analytics.top_users.slice(0, 10).map((u, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-slate-800/30 rounded-xl hover:bg-slate-800/50 transition-colors">
                <div className="flex items-center gap-3">
                  <span className={`text-sm font-bold w-6 ${i < 3 ? ['text-amber-400', 'text-slate-400', 'text-orange-400'][i] : 'text-slate-500'}`}>
                    #{i + 1}
                  </span>
                  <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold ring-2 ring-indigo-600/20">
                    {(u.username || u.first_name || '?')[0]?.toUpperCase()}
                  </div>
                  <span className="text-white font-medium">{u.username || u.first_name || `User ${u.user_id}`}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-slate-400">{u.downloads || u.total_downloads} تحميل</span>
                  <span className="text-xs text-slate-500">{u.tier || 'Free'}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


