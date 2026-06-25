import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Zap, Eye, EyeOff, Shield, Loader2, KeyRound, MessageCircle } from 'lucide-react';

export default function LoginPage() {
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState('password'); // password | otp
  const [otp, setOTP] = useState('');

  const { login, verifyOTP, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      const from = location.state?.from || '/';
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, location.state]);

  // ── Step 1: Submit password → request OTP ──
  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    if (!password.trim()) {
      setError('الرجاء إدخال كلمة المرور');
      return;
    }

    setError('');
    setLoading(true);
    try {
      await login(password.trim());
      setStep('otp');
    } catch (err) {
      setError(
        err.response?.data?.message ||
        err.message ||
        'كلمة المرور غير صحيحة'
      );
    }
    setLoading(false);
  };

  // ── Step 2: Submit OTP → get token ──
  const handleOTPSubmit = async (e) => {
    e.preventDefault();
    if (otp.length < 6) {
      setError('الرجاء إدخال رمز التحقق كاملاً');
      return;
    }

    setError('');
    setLoading(true);
    try {
      await verifyOTP(otp);
      // AuthContext will set user and the useEffect above will redirect
    } catch (err) {
      setError(
        err.response?.data?.message ||
        err.message ||
        'رمز التحقق غير صحيح'
      );
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-950 via-slate-950 to-indigo-950 p-4">
      {/* Background glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-indigo-600/5 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-600 mb-4 shadow-lg shadow-indigo-500/30 animate-glow">
            {step === 'password' ? (
              <KeyRound className="w-8 h-8 text-white" />
            ) : (
              <MessageCircle className="w-8 h-8 text-white" />
            )}
          </div>
          <h1 className="text-2xl font-bold gradient-text">ساحِب</h1>
          <p className="text-slate-500 mt-1">
            {step === 'password'
              ? 'لوحة تحكم البوت — أدخل كلمة المرور'
              : 'تم إرسال رمز تحقق إلى تيليجرام'}
          </p>
        </div>

        {/* Card */}
        <div className="card-accent animate-in">
          {step === 'password' ? (
            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1.5">كلمة المرور</label>
                <div className="relative">
                  <input
                    type={showPw ? 'text' : 'password'}
                    className="input-field pr-10"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoFocus
                    autoComplete="current-password"
                    dir="ltr"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(!showPw)}
                    className="absolute left-3 top-1/2 -translate-y-1/2 p-1 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
                    tabIndex={-1}
                  >
                    {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-xs text-slate-600 mt-2">
                  سيتم إرسال رمز تحقق إلى حساب تيليجرام المسجل
                </p>
              </div>

              {error && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-2.5 text-sm text-red-400 animate-in">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full btn btn-primary py-2.5 text-base"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    جاري التحقق...
                  </span>
                ) : (
                  <span className="flex items-center justify-center gap-2">
                    <KeyRound className="w-4 h-4" />
                    متابعة
                  </span>
                )}
              </button>
            </form>
          ) : (
            <form onSubmit={handleOTPSubmit} className="space-y-4">
              <div className="text-center space-y-3">
                <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto">
                  <Shield className="w-6 h-6 text-indigo-400" />
                </div>
                <div>
                  <p className="text-sm text-slate-300">تم إرسال رمز التحقق</p>
                  <p className="text-xs text-slate-500 mt-1">
                    تفقد رسائل تيليجرام من البوت — الرمز صالح لمدة 5 دقائق
                  </p>
                </div>
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-1.5">رمز التحقق</label>
                <input
                  type="text"
                  className="input-field text-center text-2xl tracking-[0.3em] font-mono"
                  placeholder="000000"
                  value={otp}
                  onChange={(e) => setOTP(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  maxLength={6}
                  required
                  autoFocus
                  autoComplete="one-time-code"
                  dir="ltr"
                />
              </div>

              {error && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-2.5 text-sm text-red-400 animate-in">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading || otp.length < 6}
                className="w-full btn btn-primary py-2.5 text-base"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    جاري التحقق...
                  </span>
                ) : (
                  'تأكيد'
                )}
              </button>
              <button
                type="button"
                onClick={() => { setStep('password'); setError(''); setOTP(''); }}
                className="w-full btn btn-ghost py-2.5"
              >
                رجوع
              </button>
            </form>
          )}
        </div>

        <p className="text-center text-xs text-slate-600 mt-6">
          TikTokForBot Admin © {new Date().getFullYear()}
        </p>
      </div>
    </div>
  );
}
