import { Link } from 'react-router-dom';
import { Home, Search } from 'lucide-react';

export default function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 p-4">
      {/* Background glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-purple-600/10 rounded-full blur-3xl" />
      </div>

      <div className="relative text-center max-w-md">
        {/* 404 Number */}
        <div className="text-[120px] font-black leading-none gradient-text select-none">
          404
        </div>

        {/* Icon */}
        <div className="w-20 h-20 rounded-2xl bg-slate-800/50 border border-slate-700/50 flex items-center justify-center mx-auto -mt-4 mb-6">
          <Search className="w-10 h-10 text-slate-500" />
        </div>

        <h1 className="text-2xl font-bold text-white mb-2">الصفحة غير موجودة</h1>
        <p className="text-slate-500 mb-8 leading-relaxed">
          الصفحة التي تبحث عنها غير موجودة أو تم نقلها. تأكد من الرابط وحاول مرة أخرى.
        </p>

        <div className="flex gap-3 justify-center">
          <Link to="/" className="btn btn-primary inline-flex items-center gap-2">
            <Home className="w-4 h-4" />
            العودة للرئيسية
          </Link>
        </div>
      </div>
    </div>
  );
}
