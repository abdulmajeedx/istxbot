import { useState, useMemo } from 'react';
import {
  ChevronUp, ChevronDown, ChevronsUpDown, MessageSquare,
  Ban, Crown, Trash2, Copy, CheckCheck, Clock,
} from 'lucide-react';
import CopyToClipboard from './CopyToClipboard';
import EmptyState from './EmptyState';
import TierBadge from './TierBadge';
import { Users as UsersIcon } from 'lucide-react';

// ── دوال مساعدة لعرض اسم المستخدم بنسق تليجرام ──────────────────

function cleanName(str) {
  if (!str || typeof str !== 'string') return '';
  return str.trim(); 
}

/** الاسم الكامل بنسق تليجرام: "First Last" */
function displayName(u) {
  const first = cleanName(u.first_name);
  const last = cleanName(u.last_name);
  const username = cleanName(u.username);

  // لو الاسم الأول موجود
  if (first) {
    // أضف الاسم الأخير لو موجود ومختلف عن الأول
    if (last && last !== first) return `${first} ${last}`;
    return first;
  }
  // لو فقط اسم أخير
  if (last) return last;
  // يوزر كاسم عرض
  if (username) return username;
  // لا شيء — عرض معرف مختصر
  return `مستخدم ${String(u.user_id).slice(-4)}`;
}

/** السطر الثاني — @username فقط (مثل تليجرام) */
function displaySub(u) {
  const username = cleanName(u.username);
  return username ? `@${username}` : '';
}

/** الحرف الأول للصورة الرمزية */
function displayInitial(u) {
  const first = cleanName(u.first_name);
  const last = cleanName(u.last_name);
  const username = cleanName(u.username);
  if (first) return first[0].toUpperCase();
  if (last) return last[0].toUpperCase();
  if (username) return username[0].toUpperCase();
  return String(u.user_id).slice(-2);
}

const SortIcon = ({ direction }) => {
  if (!direction) return <ChevronsUpDown className="w-3.5 h-3.5 inline opacity-40" />;
  return direction === 'asc'
    ? <ChevronUp className="w-3.5 h-3.5 inline text-indigo-400" />
    : <ChevronDown className="w-3.5 h-3.5 inline text-indigo-400" />;
};

export default function UserTable({
  users,
  loading,
  selectedIds,
  onSelect,
  onSelectAll,
  onUserClick,
  onMessage,
  onBan,
  onPromote,
  onDelete,
  sortField,
  sortDir,
  onSort,
  page,
  totalPages,
  total,
  onPageChange,
}) {
  const allSelected = users.length > 0 && selectedIds.length === users.length;
  const someSelected = selectedIds.length > 0 && !allSelected;

  const columns = useMemo(() => [
    { key: 'checkbox', label: '', sortable: false, width: 'w-10' },
    { key: 'user', label: 'المستخدم', sortable: true, width: '' },
    { key: 'user_id', label: 'ID', sortable: true, width: 'w-28' },
    { key: 'tier', label: 'المستوى', sortable: true, width: 'w-20' },
    { key: 'expiry', label: 'الصلاحية', sortable: false, width: 'w-24' },
    { key: 'visit_count', label: 'الزيارات', sortable: true, width: 'w-16 text-center' },
    { key: 'is_banned', label: 'الحالة', sortable: true, width: 'w-20' },
    { key: 'last_visit', label: 'آخر نشاط', sortable: true, width: 'w-28' },
    { key: 'actions', label: 'الإجراءات', sortable: false, width: 'w-36' },
  ], []);

  const handleSort = (key) => {
    if (key === 'checkbox' || key === 'actions') return;
    onSort(key);
  };

  if (loading) {
    return (
      <div className="card overflow-hidden p-0">
        <div className="animate-pulse">
          <div className="flex items-center gap-4 p-4 bg-slate-800/30 border-b border-slate-700/50">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="h-4 flex-1 skeleton rounded" />
            ))}
          </div>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 p-4 border-b border-slate-800/50">
              <div className="w-4 h-4 skeleton rounded" />
              <div className="w-9 h-9 skeleton rounded-full" />
              <div className="h-4 flex-1 skeleton rounded" />
              <div className="h-4 w-20 skeleton rounded" />
              <div className="h-4 w-16 skeleton rounded" />
              <div className="h-4 w-12 skeleton rounded" />
              <div className="h-4 w-16 skeleton rounded" />
              <div className="h-4 w-28 skeleton rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (users.length === 0) {
    return (
      <div className="card">
        <EmptyState
          icon={UsersIcon}
          title="لا توجد نتائج"
          description="حاول تغيير معايير البحث أو الفلترة"
        />
      </div>
    );
  }

  return (
    <div className="card overflow-hidden p-0">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-800/50">
            <tr className="text-slate-400 text-right">
              <th className="p-4 w-10">
                <input
                  type="checkbox"
                  checked={allSelected}
                  ref={(el) => { if (el) el.indeterminate = someSelected; }}
                  onChange={() => onSelectAll(allSelected ? [] : users.map((u) => u.user_id))}
                  className="rounded border-slate-600 bg-slate-800 text-indigo-600 focus:ring-indigo-600"
                />
              </th>
              {columns.slice(1).map((col) => (
                <th
                  key={col.key}
                  className={`p-4 font-medium ${col.width} ${col.sortable ? 'cursor-pointer hover:text-white select-none' : ''}`}
                  onClick={() => handleSort(col.key)}
                >
                  {col.label}
                  {col.sortable && ` ${' '}`}
                  {col.sortable && <SortIcon direction={sortField === col.key ? sortDir : null} />}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {users.map((u) => {
              const isSelected = selectedIds.includes(u.user_id);
              return (
                <tr
                  key={u.user_id}
                  className={`hover:bg-slate-800/30 transition-colors cursor-pointer ${
                    isSelected ? 'bg-indigo-600/5' : ''
                  }`}
                  onClick={() => onUserClick(u)}
                >
                  <td className="p-4" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => onSelect(u.user_id)}
                      className="rounded border-slate-600 bg-slate-800 text-indigo-600 focus:ring-indigo-600"
                    />
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-xs font-bold ring-2 ring-indigo-600/20 shrink-0">
                        {displayInitial(u)}
                      </div>
                      <div>
                        <p className="font-medium text-white text-sm">{displayName(u)}</p>
                        <p className="text-xs text-slate-500">{displaySub(u)}</p>
                      </div>
                    </div>
                  </td>
                  <td className="p-4 text-slate-400 font-mono text-xs">
                    <div className="flex items-center gap-1.5">
                      <span>{u.user_id}</span>
                      <CopyToClipboard text={String(u.user_id)} iconOnly />
                    </div>
                  </td>
                  <td className="p-4"><TierBadge tier={u.tier || 'free'} /></td>
                <td className="p-4 text-xs text-slate-500">
                  {u.tier_expires_at ? new Date(u.tier_expires_at * 1000).toLocaleDateString('ar-SA', {
                    day: 'numeric', month: 'short', year: 'numeric',
                  }) : 'دائمة'}
                </td>
                  <td className="p-4 text-white font-medium text-center">{u.visit_count || 0}</td>
                  <td className="p-4">
                    {u.is_banned ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-500/10 text-red-400 border border-red-500/20">
                        <Ban className="w-3 h-3" /> محظور
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        <CheckCheck className="w-3 h-3" /> نشط
                      </span>
                    )}
                  </td>
                  <td className="p-4 text-xs text-slate-500">
                    {u.last_visit ? new Date(u.last_visit).toLocaleDateString('ar-SA', {
                      day: 'numeric', month: 'short', year: 'numeric',
                    }) : '—'}
                  </td>
                  <td className="p-4" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => onMessage(u)}
                        className="p-2 rounded-lg hover:bg-indigo-500/10 text-slate-400 hover:text-indigo-400 transition-colors"
                        title="مراسلة"
                      >
                        <MessageSquare className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => onBan(u)}
                        className={`p-2 rounded-lg transition-colors ${
                          u.is_banned
                            ? 'hover:bg-emerald-500/10 text-slate-400 hover:text-emerald-400'
                            : 'hover:bg-red-500/10 text-slate-400 hover:text-red-400'
                        }`}
                        title={u.is_banned ? 'فك الحظر' : 'حظر'}
                      >
                        <Ban className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => onPromote(u.user_id)}
                        className="p-2 rounded-lg hover:bg-amber-500/10 text-slate-400 hover:text-amber-400 transition-colors"
                        title="ترقية"
                      >
                        <Crown className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => onDelete(u)}
                        className="p-2 rounded-lg hover:bg-red-500/10 text-slate-400 hover:text-red-400 transition-colors"
                        title="حذف"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between p-4 border-t border-slate-800">
          <span className="text-xs text-slate-500">
            صفحة {page} من {totalPages} ({total} مستخدم)
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              السابق
            </button>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              التالي
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
