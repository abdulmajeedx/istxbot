import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { auth, getStoredToken, setStoredToken } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);

  const validatedRef = useRef(false);

  const buildUser = useCallback((token) => {
    if (!token) return null;
    return {
      username: 'Admin',
      role: 'admin',
      loginTime: Date.now(),
      lastActivity: Date.now(),
      token,
    };
  }, []);

  // ── Restore & validate session from stored token ──
  const restoreSession = useCallback(async () => {
    if (validatedRef.current) return;
    validatedRef.current = true;

    const token = getStoredToken();
    if (!token) {
      setLoading(false);
      return false;
    }

    try {
      await auth.checkSession();
      const userData = buildUser(token);
      setUser(userData);
      setLoading(false);
      return true;
    } catch {
      setStoredToken(null);
      setUser(null);
      setLoading(false);
      return false;
    }
  }, [buildUser]);

  // ── Step 1: Request OTP ──
  const login = useCallback(async (password) => {
    const { data } = await auth.requestOTP(password);

    if (!data?.success) {
      throw new Error(data?.message || 'كلمة المرور غير صحيحة');
    }

    return { needOTP: true };
  }, []);

  // ── Step 2: Verify OTP ──
  const verifyOTP = useCallback(async (code) => {
    const { data } = await auth.verifyOTP(code);

    if (!data?.success || !data?.token) {
      throw new Error(data?.message || 'رمز التحقق غير صحيح');
    }

    setStoredToken(data.token);

    const userData = {
      username: data.username || 'Admin',
      role: data.role || 'admin',
      loginTime: Date.now(),
      lastActivity: Date.now(),
      token: data.token,
    };
    setUser(userData);
    return { success: true };
  }, []);

  // ── Logout ──
  const logout = useCallback(async () => {
    try {
      await auth.logout();
    } catch {
      // Even if server call fails, clear local state
    }
    validatedRef.current = false;
    setStoredToken(null);
    setUser(null);
  }, []);

  // ── Update last activity ──
  const updateActivity = useCallback(() => {
    setUser((prev) => (prev ? { ...prev, lastActivity: Date.now() } : null));
  }, []);

  // ── Initial session restore + validation on mount ──
  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  // ── Listen for session-expired event from axios interceptor ──
  useEffect(() => {
    const handler = () => {
      validatedRef.current = false;
      setStoredToken(null);
      setUser(null);
    };
    window.addEventListener('auth:session-expired', handler);
    return () => window.removeEventListener('auth:session-expired', handler);
  }, []);

  const value = {
    user,
    loading,
    login,
    verifyOTP,
    logout,
    restoreSession,
    updateActivity,
    isAuthenticated: !!user,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}

export default AuthContext;

