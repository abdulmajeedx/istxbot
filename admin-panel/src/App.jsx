import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ToastProvider } from './components/Toast';
import ErrorBoundary from './components/ErrorBoundary';
import ProtectedRoute from './components/ProtectedRoute';
import DashboardLayout from './layouts/DashboardLayout';
import CommandPalette from './components/CommandPalette';
import ShortcutsOverlay from './components/ShortcutsOverlay';

import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import UsersPage from './pages/UsersPage';
import AnalyticsPage from './pages/AnalyticsPage';
import SettingsPage from './pages/SettingsPage';
import LogsPage from './pages/LogsPage';
import BroadcastPage from './pages/BroadcastPage';
import DatabasePage from './pages/DatabasePage';
import SystemPage from './pages/SystemPage';
import TiersPage from './pages/TiersPage';
import NotFoundPage from './pages/NotFoundPage';

export default function App() {
  return (
    <BrowserRouter basename="/admin">
      <AuthProvider>
        <ErrorBoundary>
          <ToastProvider>
            <Routes>
              {/* Public */}
              <Route path="/login" element={<LoginPage />} />

              {/* Protected Dashboard Routes */}
              <Route
                element={
                  <ProtectedRoute>
                    <DashboardLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<DashboardPage />} />
                <Route path="users" element={<UsersPage />} />
                <Route path="analytics" element={<AnalyticsPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="logs" element={<LogsPage />} />
                <Route path="broadcast" element={<BroadcastPage />} />
                <Route path="database" element={<DatabasePage />} />
                <Route path="system" element={<SystemPage />} />
                <Route path="tiers" element={<TiersPage />} />
              </Route>

              {/* 404 */}
              <Route path="*" element={<NotFoundPage />} />
            </Routes>

            {/* Global overlays — inside ToastProvider so they can use toast */}
            <CommandPalette />
            <ShortcutsOverlay />
          </ToastProvider>
        </ErrorBoundary>
      </AuthProvider>
    </BrowserRouter>
  );
}
