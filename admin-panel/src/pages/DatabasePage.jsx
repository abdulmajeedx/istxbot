import { useState, useEffect, useCallback } from 'react';
import { database } from '../api/client';
import { useToast } from '../components/Toast';
import ConfirmDialog from '../components/ConfirmDialog';
import { HardDrive, Download, Terminal, Database, Loader2, Clock } from 'lucide-react';

export default function DatabasePage() {
  const { toast } = useToast();
  const [dbInfo, setDbInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [backingUp, setBackingUp] = useState(false);
  const [queryMode, setQueryMode] = useState(false);
  const [sqlQuery, setSqlQuery] = useState('');
  const [queryResult, setQueryResult] = useState(null);
  const [queryRunning, setQueryRunning] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const loadInfo = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await database.info();
      setDbInfo(data);
    } catch (err) {
      toast.error('فشل تحميل معلومات قاعدة البيانات');
    }
    setLoading(false);
  }, [toast]);

  useEffect(() => { loadInfo(); }, [loadInfo]);

  const handleBackup = async () => {
    setBackingUp(true);
    try {
      await database.backup();
      toast.success('تم إنشاء نسخة احتياطية بنجاح');
      loadInfo();
    } catch (err) {
      toast.error('فشل إنشاء نسخة احتياطية');
    }
    setBackingUp(false);
  };

  const handleQuery = async () => {
    if (!sqlQuery.trim()) return;
    setQueryRunning(true);
    setQueryResult(null);
    try {
      const { data } = await database.query(sqlQuery.trim());
      setQueryResult(data);
      toast.success('تم تنفيذ الاستعلام');
    } catch (err) {
      toast.error(err.response?.data?.message || 'فشل تنفيذ الاستعلام');
    }
    setQueryRunning(false);
  };

  const handleDelete = async () => {
    setShowDeleteConfirm(false);
    try {
      await database.delete();
      toast.success('تم حذف قاعدة البيانات');
      loadInfo();
    } catch (err) {
      toast.error('فشل حذف قاعدة البيانات');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">قاعدة البيانات</h2>
        <p className="text-slate-500 text-sm mt-1">إدارة وصيانة قاعدة بيانات البوت</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xl font-bold text-white">{dbInfo?.size || '-'}</p>
            <p className="text-xs text-slate-500">الحجم</p>
          </div>
        </div>
        <div className="card flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <HardDrive className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xl font-bold text-white">{dbInfo?.tables || '-'}</p>
            <p className="text-xs text-slate-500">الجداول</p>
          </div>
        </div>
        <div className="card flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <Download className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xl font-bold text-white">{dbInfo?.backups || '-'}</p>
            <p className="text-xs text-slate-500">النسخ الاحتياطية</p>
          </div>
        </div>
        <div className="card flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <Clock className="w-5 h-5" />
          </div>
          <div>
            <p className="text-sm font-bold text-white">{dbInfo?.last_backup || 'لا يوجد'}</p>
            <p className="text-xs text-slate-500">آخر نسخة احتياطية</p>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="card space-y-4">
        <h3 className="text-lg font-semibold text-white">الإجراءات</h3>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={handleBackup}
            disabled={backingUp}
            className="btn btn-primary flex items-center gap-2"
          >
            {backingUp ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            {backingUp ? 'جاري النسخ...' : 'نسخ احتياطي الآن'}
          </button>
          <button
            onClick={() => setQueryMode(!queryMode)}
            className={`btn flex items-center gap-2 ${queryMode ? 'bg-indigo-600 text-white' : 'btn-ghost'}`}
          >
            <Terminal className="w-4 h-4" />
            استعلام SQL
          </button>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="btn btn-danger flex items-center gap-2"
          >
            حذف قاعدة البيانات
          </button>
        </div>
      </div>

      {/* SQL Query */}
      {queryMode && (
        <div className="card space-y-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Terminal className="w-5 h-5 text-indigo-400" />
            استعلام SQL
          </h3>
          <textarea
            className="input-field h-32 font-mono resize-y"
            placeholder="SELECT * FROM users LIMIT 10;"
            value={sqlQuery}
            onChange={(e) => setSqlQuery(e.target.value)}
            dir="ltr"
          />
          <div className="flex items-center gap-3">
            <button
              onClick={handleQuery}
              disabled={queryRunning || !sqlQuery.trim()}
              className="btn btn-primary flex items-center gap-2"
            >
              {queryRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Terminal className="w-4 h-4" />}
              تنفيذ
            </button>
          </div>

          {/* Query Result */}
          {queryResult && (
            <div className="mt-4">
              <h4 className="text-sm font-semibold text-slate-400 mb-2">النتيجة</h4>
              <pre className="bg-slate-900 border border-slate-700 rounded-xl p-4 text-xs text-slate-300 overflow-auto max-h-64" dir="ltr">
                {typeof queryResult === 'string' ? queryResult : JSON.stringify(queryResult, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* DB Details */}
      {dbInfo?.details && (
        <div className="card space-y-4">
          <h3 className="text-lg font-semibold text-white">معلومات إضافية</h3>
          <pre className="bg-slate-900 border border-slate-700 rounded-xl p-4 text-xs text-slate-300 overflow-auto max-h-64" dir="ltr">
            {JSON.stringify(dbInfo.details, null, 2)}
          </pre>
        </div>
      )}

      {/* Confirm Delete */}
      <ConfirmDialog
        open={showDeleteConfirm}
        title="حذف قاعدة البيانات"
        message="هل أنت متأكد من حذف قاعدة البيانات بالكامل؟ هذا الإجراء لا يمكن التراجع عنه وسيؤدي إلى فقدان جميع البيانات!"
        confirmText="نعم، احذف"
        cancelText="إلغاء"
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </div>
  );
}
