import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { getStoredToken } from '../api/client';
import { SkeletonPulse } from './Skeleton';
import { Loader2 } from 'lucide-react';

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  // Quick check: if we have a stored token, user should be set already
  // (happens synchronously in AuthProvider mount)
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <div className="relative text-center space-y-6">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-indigo-600/5 rounded-full blur-3xl" />
          <div className="relative space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-indigo-600/20 border border-indigo-600/20 flex items-center justify-center mx-auto">
              <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
            </div>
            <div className="space-y-3">
              <SkeletonPulse className="h-7 w-40 mx-auto rounded-lg" />
              <SkeletonPulse className="h-4 w-56 mx-auto rounded-lg" />
            </div>
            <p className="text-sm text-slate-500">جار التحقق من الجلسة...</p>
          </div>
        </div>
      </div>
    );
  }

  if (!user && !getStoredToken()) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  // If we have token but user is still null (race condition), show loading
  if (!user && getStoredToken()) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  return children;
}

