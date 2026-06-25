import { useState, useCallback } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../components/Toast';
import PageTransition from '../components/PageTransition';
import useIdleTimeout, { formatTimeRemaining } from '../hooks/useIdleTimeout';
import {
  LayoutDashboard, Users, Settings, ScrollText,
  BarChart3, LogOut, Zap, Radio, Database, Server,
  ChevronRight, Menu, X, ChevronLeft, AlertTriangle, Clock, Shield,
} from 'lucide-react';

const mainNavItems = [
  { to: '/', icon: LayoutDashboard, label: 'الرئيسية', end: true },
  { to: '/users', icon: Users, label: 'المستخدمين' },
  { to: '/analytics', icon: BarChart3, label: 'التحليلات' },
  { to: '/settings', icon: Settings, label: 'الإعدادات' },
  { to: '/logs', icon: ScrollText, label: 'السجلات' },
];

const adminNavItems = [
  { to: '/broadcast', icon: Radio, label: 'رسالة جماعية' },
  { to: '/tiers', icon: Shield, label: 'المستويات' },
  { to: '/database', icon: Database, label: 'قاعدة البيانات' },
  { to: '/system', icon: Server, label: 'النظام' },
];

export default function DashboardLayout() {
  const { user, logout, updateActivity } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [idleWarning, setIdleWarning] = useState(false);

  // ── Idle Timeout ──
  const handleIdleWarning = useCallback(() => {
    setIdleWarning(true);
    toast.warning('لم يتم اكتشاف أي نشاط. سيتم تسجيل الخروج تلقائياً خلال 15 دقيقة.');
  }, [toast]);

  const handleIdleLogout = useCallback(async () => {
    setIdleWarning(false);
    toast.error('تم تسجيل الخروج تلقائياً بسبب عدم النشاط.');
    await logout();
    navigate('/login');
  }, [logout, navigate, toast]);

  const { resetTimer, timeUntilLogout } = useIdleTimeout({
    warnAfter: 15 * 60 * 1000,   // 15 min
    logoutAfter: 30 * 60 * 1000,  // 30 min
    onWarning: handleIdleWarning,
    onLogout: handleIdleLogout,
    enabled: !!user, // Only track when logged in
  });

  // Reset idle timer on any user interaction in the layout
  const handleUserActivity = useCallback(() => {
    resetTimer();
    updateActivity();
    if (idleWarning) setIdleWarning(false);
  }, [resetTimer, updateActivity, idleWarning]);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  // Get current page for breadcrumb
  const allItems = [...mainNavItems, ...adminNavItems];
  const currentItem = allItems.find(
    (item) =>
      item.end
        ? location.pathname === '/'
        : location.pathname.startsWith(item.to) && item.to !== '/'
  );
  const currentLabel = currentItem?.label || 'لوحة التحكم';

  const sidebarContent = (
    <div className="h-full flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-slate-700/50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center shrink-0 shadow-lg shadow-indigo-500/30">
            <Zap className="w-5 h-5 text-white" />
          </div>
          {!collapsed && (
            <div className="overflow-hidden">
              <h1 className="text-lg font-bold gradient-text">ساحِب</h1>
              <p className="text-xs text-slate-500">لوحة التحكم</p>
            </div>
          )}
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-4 space-y-1 overflow-y-auto scrollbar-thin">
        <p className={`text-xs text-slate-600 mb-2 px-3 ${collapsed ? 'text-center' : ''}`}>
          {collapsed ? '—' : 'القائمة الرئيسية'}
        </p>
        {mainNavItems.map(({ to, icon: Icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group relative ${
                isActive
                  ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`
            }
            title={collapsed ? label : undefined}
          >
            <Icon className="w-5 h-5 shrink-0" />
            {!collapsed && <span>{label}</span>}
            {collapsed && (
              <span className="absolute right-full mr-3 px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-white whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-xl">
                {label}
              </span>
            )}
          </NavLink>
        ))}

        <div className="my-3 border-t border-slate-800" />

        <p className={`text-xs text-slate-600 mb-2 px-3 ${collapsed ? 'text-center' : ''}`}>
          {collapsed ? '—' : 'الإدارة'}
        </p>
        {adminNavItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group relative ${
                isActive
                  ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`
            }
            title={collapsed ? label : undefined}
          >
            <Icon className="w-5 h-5 shrink-0" />
            {!collapsed && <span>{label}</span>}
            {collapsed && (
              <span className="absolute right-full mr-3 px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-white whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-xl">
                {label}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="hidden lg:flex items-center justify-center h-10 mx-4 mb-1 rounded-xl hover:bg-slate-800/50 text-slate-600 hover:text-slate-400 transition-colors border border-transparent hover:border-slate-700/50"
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>

      {/* User & Logout */}
      <div className="p-4 border-t border-slate-700/50">
        <div className={`flex items-center gap-3 mb-3 ${collapsed ? 'justify-center' : ''}`}>
          <div className="w-9 h-9 rounded-full bg-indigo-600 flex items-center justify-center text-sm font-bold shrink-0">
            {user?.username?.[0]?.toUpperCase() || 'A'}
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-slate-200 truncate">{user?.username || 'Admin'}</p>
              <p className="text-xs text-slate-500">{user?.role === 'admin' ? 'مدير النظام' : 'مشرف'}</p>
            </div>
          )}
        </div>
        <button
          onClick={handleLogout}
          className={`flex items-center gap-2 w-full px-3 py-2 rounded-xl text-sm text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-all ${collapsed ? 'justify-center' : ''}`}
        >
          <LogOut className="w-4 h-4 shrink-0" />
          {!collapsed && 'تسجيل الخروج'}
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-gray-950" onClick={handleUserActivity}>
      {/* Desktop Sidebar */}
      <aside className={`hidden lg:flex flex-col glass border-l border-slate-700/50 transition-all duration-300 ${collapsed ? 'w-[72px]' : 'w-64'}`}>
        {sidebarContent}
      </aside>

      {/* Mobile Sidebar Overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <aside className="absolute right-0 top-0 bottom-0 w-72 glass border-l border-slate-700/50 shadow-2xl animate-slide-in-right">
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Mobile Header */}
        <header className="lg:hidden flex items-center gap-3 p-4 border-b border-slate-800">
          <button onClick={() => setMobileOpen(true)} className="p-2 rounded-xl hover:bg-slate-800 text-slate-400">
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-indigo-400" />
            <h1 className="text-sm font-bold text-white">ساحِب</h1>
          </div>
        </header>

        {/* Breadcrumb */}
        <div className="hidden lg:flex items-center gap-2 px-6 py-3 border-b border-slate-800/50 text-sm">
          <span className="text-slate-600">الرئيسية</span>
          <ChevronRight className="w-3 h-3 text-slate-700" />
          <span className="text-slate-400">{currentLabel}</span>
        </div>

        {/* Idle Warning Banner */}
        {idleWarning && (
          <div className="flex items-center gap-3 px-6 py-2.5 bg-amber-500/10 border-b border-amber-500/20 text-sm text-amber-400 animate-in">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span className="flex-1">
              لم يتم اكتشاف أي نشاط. سيتم تسجيل الخروج تلقائياً خلال {formatTimeRemaining(timeUntilLogout)}.
            </span>
            <button onClick={() => { resetTimer(); setIdleWarning(false); }} className="flex items-center gap-1 px-3 py-1 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 text-xs font-medium transition-colors">
              <Clock className="w-3 h-3" />
              أنا هنا
            </button>
          </div>
        )}

        {/* Page Content */}
        <div className="flex-1 overflow-y-auto p-4 lg:p-6">
          <PageTransition triggerKey={location.pathname}>
            <Outlet />
          </PageTransition>
        </div>
      </main>
    </div>
  );
}
