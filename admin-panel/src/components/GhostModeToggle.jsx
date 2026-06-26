import { useState } from 'react';
import { Ghost, History, EyeOff, ShieldAlert } from 'lucide-react';
import ConfirmDialog from './ConfirmDialog';

/**
 * مكون مفتاح تبديل وضع الشبح (Ghost Mode Toggle)
 *
 * عند تفعيله: جميع تغييرات المستويات تتم بصمت دون إشعار المستخدمين
 * Props:
 *   ghostMode    - boolean: حالة وضع الشبح
 *   onToggle     - (enabled: boolean) => void: دالة التبديل
 *   onShowHistory - () => void: دالة عرض سجل العمليات
 */
export default function GhostModeToggle({ ghostMode, onToggle, onShowHistory }) {


  const handleToggle = () => {
    if (ghostMode) {
      // عند التعطيل: مباشر بدون تأكيد
      onToggle(false);
    } else {
      // عند التفعيل: طلب تأكيد
      setShowConfirm(true);
    }
  };

  return (
    <>
      {/* ═══ بطاقة التحكم بوضع الشبح ═══ */}
      <div className={`card transition-all duration-300 ${
        ghostMode
          ? 'border-indigo-600/30 bg-gradient-to-r from-indigo-600/5 to-purple-600/5'
          : 'border-slate-700/50'
      }`}>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          {/* الجانب الأيمن: الأيقونة والمفتاح */}
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center border transition-colors ${
              ghostMode
                ? 'bg-indigo-500/15 border-indigo-500/30 text-indigo-400'
                : 'bg-slate-800 border-slate-700 text-slate-500'
            }`}>
              {ghostMode ? (
                <Ghost className="w-5 h-5" />
              ) : (
                <EyeOff className="w-5 h-5" />
              )}
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                وضع الشبح
                {ghostMode && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-600/20 text-indigo-400 border border-indigo-600/30">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
                    مفعل
                  </span>
                )}
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                {ghostMode
                  ? 'جميع تغييرات المستويات لا ترسل إشعارات'
                  : 'فعّل لتعديل المستويات بدون إشعار المستخدمين'}
              </p>
            </div>
          </div>

          {/* الجانب الأيسر: المفتاح وزر السجل */}
          <div className="flex items-center gap-3">
            {/* زر سجل التغييرات */}
            <button
              onClick={onShowHistory}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-slate-800 border border-slate-700 text-slate-400 hover:text-white hover:border-slate-600 transition-colors"
              title="سجل تغييرات الشبح"
            >
              <History className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">سجل التغييرات</span>
            </button>

            {/* مفتاح التبديل */}
            <button
              onClick={handleToggle}
              className={`relative inline-flex h-7 w-12 items-center rounded-full transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900 ${
                ghostMode
                  ? 'bg-gradient-to-r from-indigo-600 to-purple-600 focus:ring-indigo-500 shadow-lg shadow-indigo-600/25'
                  : 'bg-slate-700 focus:ring-slate-500'
              }`}
              role="switch"
              aria-checked={ghostMode}
              title={ghostMode ? 'تعطيل وضع الشبح' : 'تفعيل وضع الشبح'}
            >
              <span
                className={`inline-flex h-5 w-5 items-center justify-center rounded-full bg-white shadow-md transform transition-transform duration-300 ${
                  ghostMode ? 'translate-x-6' : 'translate-x-1'
                }`}
              >
                {ghostMode ? (
                  <Ghost className="w-3 h-3 text-indigo-600" />
                ) : (
                  <EyeOff className="w-3 h-3 text-slate-400" />
                )}
              </span>
            </button>
          </div>
        </div>

        {/* ═══ Banner التنبيه عند تفعيل وضع الشبح ═══ */}
        {ghostMode && (
          <div className="mt-4 flex items-start gap-3 p-3 rounded-xl bg-indigo-600/10 border border-indigo-600/20 animate-in fade-in slide-in-from-top-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-600/20 flex items-center justify-center shrink-0 mt-0.5">
              <ShieldAlert className="w-4 h-4 text-indigo-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-indigo-300">
                وضع الشبح مفعل - جميع تغييرات المستويات صامتة ولا ترسل أي إشعارات للمستخدمين
              </p>
              <p className="text-xs text-indigo-400/70 mt-1">
                الترقية والإنزال وتعديل النقاط تتم بدون علم المستخدم. تأكد من استخدام هذا الوضع بحذر.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* ═══ ConfirmDialog لتأكيد تفعيل وضع الشبح ═══ */}
      <ConfirmDialog
        open={showConfirm}
        title="تفعيل وضع الشبح"
        message="سيتم تطبيق جميع تغييرات المستويات (ترقية، إنزال، تعديل نقاط) دون إشعار المستخدمين المتأثرين. هل تريد تفعيل وضع الشبح؟"
        confirmText="تفعيل"
        cancelText="إلغاء"
        variant="info"
        onConfirm={() => {
          setShowConfirm(false);
          onToggle(true);
        }}
        onCancel={() => setShowConfirm(false)}
      />
    </>
  );
}

