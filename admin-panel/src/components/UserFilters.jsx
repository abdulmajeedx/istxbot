import { Search, Filter, X } from 'lucide-react';

const TIERS = ['all', 'free', 'premium', 'vip', 'pro'];

export default function UserFilters({
  query,
  onQueryChange,
  tierFilter,
  onTierChange,
  statusFilter,
  onStatusChange,
  countryFilter,
  onCountryChange,
  countries = [],
  total,
  children,
}) {
  const hasFilters = query || tierFilter !== 'all' || statusFilter !== 'all' || countryFilter;

  return (
    <div className="card">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
          <input
            className="input-field pl-4 pr-12"
            placeholder="بحث بالاسم، ID، أو المستخدم..."
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
          />
          {query && (
            <button
              onClick={() => onQueryChange('')}
              className="absolute left-3 top-1/2 -translate-y-1/2 p-0.5 rounded hover:bg-slate-700 text-slate-500 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-500 shrink-0" />
          <div className="flex gap-1 flex-wrap">
            {TIERS.map((t) => (
              <button
                key={t}
                onClick={() => onTierChange(t)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  tierFilter === t
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                    : 'bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700'
                }`}
              >
                {t === 'all' ? 'الكل' : t}
              </button>
            ))}
          </div>
        </div>

        <select
          value={statusFilter}
          onChange={(e) => onStatusChange(e.target.value)}
          className="input-field min-w-[120px] text-sm"
        >
          <option value="all">كل الحالات</option>
          <option value="active">نشط</option>
          <option value="banned">محظور</option>
        </select>

        {countries.length > 0 && (
          <select
            value={countryFilter}
            onChange={(e) => onCountryChange(e.target.value)}
            className="input-field min-w-[130px] text-sm"
          >
            <option value="">كل الدول</option>
            {countries.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        )}

        {hasFilters && (
          <button
            onClick={() => {
              onQueryChange('');
              onTierChange('all');
              onStatusChange('all');
              onCountryChange('');
            }}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
          >
            مسح الكل
          </button>
        )}
      </div>

      <div className="mt-3 text-xs text-slate-500 flex items-center justify-between">
        <span>{total > 0 ? `إجمالي: ${total} مستخدم` : 'جاري التحميل...'}</span>
        {children && <span>{children}</span>}
      </div>
    </div>
  );
}
