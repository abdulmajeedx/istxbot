const tierColors = {
  vip: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
  premium: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/25',
  free: 'bg-slate-500/15 text-slate-400 border-slate-500/25',
};
const tierLabels = {
  vip: 'VIP',
  premium: 'بريميوم',
  free: 'مجاني',
};

export default function TierBadge({ tier, size = 'sm' }) {
  const t = (tier || 'free').toLowerCase();
  const sizeClasses = size === 'lg' ? 'px-3 py-1 text-xs' : 'px-2 py-0.5 text-[10px]';
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border font-medium ${tierColors[t] || tierColors.free} ${sizeClasses}`}>
      {tierLabels[t] || t}
    </span>
  );
}
