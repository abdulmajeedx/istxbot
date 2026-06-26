import { useState, useEffect, useCallback, useMemo } from 'react';
import { admin } from '../api/client';
import { useToast } from '../components/Toast';
import { Shield, Download, ArrowUpDown, Save, Crown, Star, Zap } from 'lucide-react';

const TIER_META = {
  vip:     { label: 'VIP',      color: 'from-purple-500 to-pink-600',      icon: Crown, bg: 'bg-purple-500/10', border: 'border-purple-500/20', text: 'text-purple-400' },
  premium: { label: 'بريميوم',   color: 'from-amber-500 to-orange-600',    icon: Star,  bg: 'bg-amber-500/10',  border: 'border-amber-500/20',  text: 'text-amber-400' },
  free:    { label: 'مجاني',     color: 'from-slate-500 to-slate-600',     icon: Zap,   bg: 'bg-slate-700',     border: 'border-slate-600',     text: 'text-slate-300' },
};

export default function TiersPage() {
  const { toast } = useToast();
  const [tiers, setTiers] = useState([]);

  const [saving, setSaving] = useState(false);


  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await admin.tierConfig.get();
      if (data?.success) setTiers(data.tiers);
    } catch {
      toast.error('فشل تحميل إعدادات المستويات');
    }
    setLoading(false);
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const updateTier = (id, field, value) => {
    setTiers((prev) => prev.map((t) => t.id === id ? { ...t, [field]: value } : t));
    setDirty(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {};
      tiers.forEach((t) => {
        payload[t.name] = {
          max_daily: t.max_daily,
          max_concurrent: t.max_concurrent,
          priority_bonus: t.priority_bonus,
        };
      });
      await admin.tierConfig.update({ tiers: payload });
      toast.success('تم حفظ إعدادات المستويات');
      setDirty(false);
    } catch {
      toast.error('فشل حفظ الإعدادات');
    }
    setSaving(false);
  };

  const totalUsers = useMemo(() => tiers.reduce((s, t) => s + (t.user_count || 0), 0), [tiers]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[1,2,3,4].map((i) => (
          <div key={i} className="card p-6 animate-pulse"><div className="h-6 skeleton rounded w-1/3 mb-4" /><div className="space-y-3">{Array.from({length:3}).map((_,j) => <div key={j} className="h-10 skeleton rounded" />)}</div></div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Shield className="w-7 h-7 text-indigo-400" />
          إدارة المستويات
        </h1>
        <button onClick={handleSave} disabled={saving || !dirty} className="btn btn-primary">
          <Save className="w-4 h-4" /> {saving ? 'جاري الحفظ...' : 'حفظ التغييرات'}
        </button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {tiers.map((tier) => {
          const meta = TIER_META[tier.id] || TIER_META.free;
          const Icon = meta.icon;
          return (
            <div key={tier.id} className="card flex items-center gap-4">
              <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${meta.color} flex items-center justify-center shadow-lg shrink-0`}>
                <Icon className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{tier.user_count}</p>
                <p className="text-xs text-slate-500">{meta.label}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {tiers.map((tier) => {
          const meta = TIER_META[tier.id] || TIER_META.free;
          const Icon = meta.icon;
          return (
            <div key={tier.id} className={`card border ${meta.border}`}>
              <div className="flex items-center gap-3 mb-5">
                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${meta.color} flex items-center justify-center`}>
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h3 className="font-semibold text-white">{meta.label}</h3>
                  <p className="text-xs text-slate-500">{tier.user_count} مستخدم</p>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs text-slate-400 mb-1.5 flex items-center gap-2">
                    <Download className="w-3.5 h-3.5" /> التحميلات اليومية
                  </label>
                  <input type="number" className="input-field" min="0" value={tier.max_daily}
                    onChange={(e) => updateTier(tier.id, 'max_daily', Math.max(0, parseInt(e.target.value) || 0))} dir="ltr" />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1.5 flex items-center gap-2">
                    <ArrowUpDown className="w-3.5 h-3.5" /> التحميلات المتزامنة
                  </label>
                  <input type="number" className="input-field" min="1" value={tier.max_concurrent}
                    onChange={(e) => updateTier(tier.id, 'max_concurrent', Math.max(1, parseInt(e.target.value) || 1))} dir="ltr" />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1.5 flex items-center gap-2">
                    <Zap className="w-3.5 h-3.5" /> أولوية التحميل (أقل = أسرع)
                  </label>
                  <input type="number" className="input-field" value={tier.priority_bonus}
                    onChange={(e) => updateTier(tier.id, 'priority_bonus', parseInt(e.target.value) || 0)} dir="ltr" />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


