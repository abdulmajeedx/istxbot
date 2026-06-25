import { useState, useEffect, useCallback, useMemo } from 'react';
import { users } from '../api/client';
import { useToast } from '../components/Toast';
import ConfirmDialog from '../components/ConfirmDialog';
import UserFilters from '../components/UserFilters';
import UserTable from '../components/UserTable';
import UserDetailPanel from '../components/UserDetailPanel';
import EmptyState from '../components/EmptyState';
import {
  Users as UsersIcon, Download, Activity, Ban, AlertTriangle, X,
} from 'lucide-react';

export default function UsersPage() {
  const { toast } = useToast();

  const [usersList, setUsersList] = useState([]);
  const [total, setTotal] = useState(null);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [countries] = useState([]);

  // Filters
  const [query, setQuery] = useState('');
  const [tierFilter, setTierFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [countryFilter, setCountryFilter] = useState('');
  const [page, setPage] = useState(1);

  // Sort
  const [sortField, setSortField] = useState('created_at');
  const [sortDir, setSortDir] = useState('desc');

  // UI
  const [selectedIds, setSelectedIds] = useState([]);
  const [detailUser, setDetailUser] = useState(null);
  const [msgTarget, setMsgTarget] = useState(null);
  const [msgText, setMsgText] = useState('');
  const [sendingMsg, setSendingMsg] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);
  const [banReason, setBanReason] = useState('');

  const [debouncedQuery, setDebouncedQuery] = useState('');
  useEffect(() => {
    const t = setTimeout(() => { setDebouncedQuery(query); setPage(1); }, 400);
    return () => clearTimeout(t);
  }, [query]);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await users.list({
        search: debouncedQuery || undefined,
        tier: tierFilter !== 'all' ? tierFilter : undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        country: countryFilter || undefined,
        page,
        per_page: 20,
        sort: sortField,
        order: sortDir,
      });

      if (Array.isArray(data)) {
        setUsersList(data);
        setTotal(data.length);
        setTotalPages(1);
      } else if (data?.users) {
        setUsersList(data.users);
        setTotal(data.total);
        setTotalPages(data.total_pages || 1);
      } else {
        setUsersList([]);
        setTotal(0);
        setTotalPages(0);
      }
    } catch {
      toast.error('فشل تحميل المستخدمين');
      setUsersList([]);
    }
    setLoading(false);
  }, [debouncedQuery, tierFilter, statusFilter, countryFilter, page, sortField, sortDir, toast]);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  const sortedUsers = useMemo(() => {
    const list = [...usersList];
    if (sortField === 'user') {
      list.sort((a, b) => {
        const va = (a.first_name || a.username || '').toLowerCase();
        const vb = (b.first_name || b.username || '').toLowerCase();
        return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
      });
    }
    return list;
  }, [usersList, sortField, sortDir]);

  const handleSort = (field) => {
    if (sortField === field) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortField(field); setSortDir('asc'); }
    setPage(1);
  };

  const handleBan = async (user, isBanned) => {
    try {
      if (isBanned) {
        await users.unban(user.user_id);
        toast.success('تم فك الحظر');
      } else {
        await users.ban(user.user_id, banReason);
        toast.success('تم حظر المستخدم');
        setBanReason('');
      }
      loadUsers();
    } catch { toast.error('فشل تنفيذ الإجراء'); }
    setConfirmAction(null);
  };

  const handleDelete = async (user) => {
    try {
      await users.delete(user.user_id);
      toast.success('تم حذف المستخدم');
      setSelectedIds((ids) => ids.filter((id) => id !== user.user_id));
      loadUsers();
    } catch { toast.error('فشل حذف المستخدم'); }
    setConfirmAction(null);
  };

  const handlePromote = async (userId) => {
    try {
      const currentTier = usersList.find((u) => u.user_id === userId)?.tier || 'free';
      const tierMap = { free: 'premium', premium: 'vip', vip: 'pro', pro: 'pro' };
      const newTier = tierMap[currentTier] || 'premium';
      const { data } = await users.setTier(userId, newTier);
      toast.success(data?.message || `تمت الترقية إلى ${newTier}`);
      loadUsers();
    } catch { toast.error('فشل ترقية المستخدم'); }
  };

  const [refreshing, setRefreshing] = useState(false);
  const handleRefreshNames = async () => {
    setRefreshing(true);
    try {
      const { admin } = await import('../api/client');
      const ids = selectedIds.length > 0 ? selectedIds : [];
      const { data } = await admin.refreshNames(ids);
      toast.success(`تم تحديث ${data.updated} اسم من تليجرام` + (data.failed ? ` (فشل: ${data.failed})` : ''));
      loadUsers();
    } catch { toast.error('فشل تحديث الأسماء'); }
    setRefreshing(false);
  };

  const handleSendMsg = async () => {
    if (!msgText.trim() || !msgTarget) return;
    setSendingMsg(true);
    try {
      const { admin } = await import('../api/client');
      await admin.sendMessage(msgTarget.user_id, msgText);
      toast.success('تم إرسال الرسالة');
      setMsgText(''); setMsgTarget(null);
    } catch { toast.error('فشل إرسال الرسالة'); }
    setSendingMsg(false);
  };

  const statCards = useMemo(() => [
    { icon: UsersIcon, label: 'إجمالي المستخدمين', value: total ?? usersList.length, color: 'from-indigo-500 to-purple-600' },
    { icon: Activity, label: 'هذه الصفحة', value: usersList.length, color: 'from-emerald-500 to-teal-600' },
    { icon: Ban, label: 'المحظورين', value: usersList.filter((u) => u.is_banned).length, color: 'from-red-500 to-rose-600' },
    { icon: Download, label: 'إجمالي التحميلات', value: usersList.reduce((s, u) => s + (u.total_downloads || 0), 0), color: 'from-amber-500 to-orange-600' },
  ], [total, usersList]);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat, i) => (
          <div key={i} className="card flex items-center gap-4">
            <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center shadow-lg shrink-0`}>
              <stat.icon className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{stat.value.toLocaleString()}</p>
              <p className="text-xs text-slate-500">{stat.label}</p>
            </div>
          </div>
        ))}
      </div>

      <UserFilters
        query={query} onQueryChange={setQuery}
        tierFilter={tierFilter} onTierChange={setTierFilter}
        statusFilter={statusFilter} onStatusChange={setStatusFilter}
        countryFilter={countryFilter} onCountryChange={setCountryFilter}
        countries={countries}
        total={total ?? usersList.length}
      >
        <button
          onClick={handleRefreshNames}
          disabled={refreshing}
          className="btn bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white flex items-center gap-2 text-sm"
          title={selectedIds.length > 0 ? 'تحديث الأسماء المحددة من تليجرام' : 'تحديث كل الأسماء الناقصة من تليجرام'}
        >
          {refreshing ? '⏳' : '🔄'} تحديث الأسماء
        </button>
      </UserFilters>

      <UserTable
        users={sortedUsers}
        loading={loading}
        selectedIds={selectedIds}
        onSelect={(id) => setSelectedIds((prev) => prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id])}
        onSelectAll={(ids) => setSelectedIds(ids)}
        onUserClick={setDetailUser}
        onMessage={setMsgTarget}
        onBan={(u) => setConfirmAction({ type: u.is_banned ? 'unban' : 'ban', user: u })}
        onPromote={handlePromote}
        onDelete={(u) => setConfirmAction({ type: 'delete', user: u })}
        sortField={sortField} sortDir={sortDir} onSort={handleSort}
        page={page} totalPages={totalPages} total={total ?? usersList.length}
        onPageChange={setPage}
      />

      {msgTarget && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={() => { setMsgTarget(null); setMsgText(''); }}>
          <div className="card w-full max-w-md animate-in zoom-in-95" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-white mb-2">مراسلة {msgTarget.first_name || (msgTarget.username ? `@${msgTarget.username}` : `#${msgTarget.user_id}`)}</h3>
            <p className="text-xs text-slate-500 mb-4">ID: {msgTarget.user_id}</p>
            <textarea className="input-field h-32 mb-3" placeholder="نص الرسالة..." value={msgText} onChange={(e) => setMsgText(e.target.value)} />
            <div className="flex gap-2">
              <button onClick={handleSendMsg} disabled={sendingMsg || !msgText.trim()} className="btn btn-primary flex-1">
                {sendingMsg ? 'جاري الإرسال...' : 'إرسال'}
              </button>
              <button onClick={() => { setMsgTarget(null); setMsgText(''); }} className="btn btn-ghost">إلغاء</button>
            </div>
          </div>
        </div>
      )}

      {confirmAction?.type === 'ban' ? (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] p-4" onClick={() => { setConfirmAction(null); setBanReason(''); }}>
          <div className="card w-full max-w-md space-y-4 animate-in zoom-in-95" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center border text-red-400 bg-red-500/10 border-red-500/20">
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <h3 className="text-lg font-semibold text-white">حظر مستخدم</h3>
              </div>
              <button onClick={() => { setConfirmAction(null); setBanReason(''); }} className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-colors"><X className="w-4 h-4" /></button>
            </div>
            <p className="text-sm text-slate-400">هل تريد حظر {confirmAction?.user?.first_name || confirmAction?.user?.username || `#${confirmAction?.user?.user_id}`}؟</p>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">سبب الحظر (سيُرسل للمستخدم)</label>
              <textarea className="input-field h-24" placeholder="اختراق، إساءة استخدام، مخالفة الشروط..." value={banReason} onChange={(e) => setBanReason(e.target.value)} />
            </div>
            <div className="flex gap-3 justify-end">
              <button onClick={() => { setConfirmAction(null); setBanReason(''); }} className="btn btn-ghost">إلغاء</button>
              <button onClick={() => handleBan(confirmAction.user, false)} className="btn btn-danger min-w-[80px]">حظر</button>
            </div>
          </div>
        </div>
      ) : (
        <ConfirmDialog
          open={!!confirmAction}
          title={confirmAction?.type === 'delete' ? 'حذف مستخدم' : 'فك حظر مستخدم'}
          message={
            confirmAction?.type === 'delete'
              ? `هل أنت متأكد من حذف ${confirmAction?.user?.first_name || confirmAction?.user?.username || `#${confirmAction?.user?.user_id}`}؟ لا يمكن التراجع عن هذا الإجراء.`
              : `هل تريد فك الحظر عن ${confirmAction?.user?.first_name || confirmAction?.user?.username || `#${confirmAction?.user?.user_id}`}؟`
          }
          confirmText={confirmAction?.type === 'delete' ? 'حذف' : 'فك الحظر'}
          cancelText="إلغاء"
          variant={confirmAction?.type === 'delete' ? 'danger' : 'warning'}
          onConfirm={() => {
            if (confirmAction?.type === 'delete') handleDelete(confirmAction.user);
            else handleBan(confirmAction.user, true);
          }}
          onCancel={() => setConfirmAction(null)}
        />
      )}

      {detailUser && <UserDetailPanel user={detailUser} onClose={() => setDetailUser(null)} onRefresh={loadUsers} />}
    </div>
  );
}
