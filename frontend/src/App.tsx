import { Routes, Route, Navigate } from 'react-router';
import { Component, useEffect, useState, type ReactNode } from 'react';
import { clearToken, isAuthenticated } from './auth';
import { api } from './api';
import Layout from './components/Layout';
import AdminLayout from './components/AdminLayout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import AdminDashboard from './pages/AdminDashboard';
import News from './pages/News';
import Runs from './pages/Runs';
import Config from './pages/Config';
import Usage from './pages/Usage';
import Logs from './pages/Logs';

function ProtectedRoute({ children }: { children: ReactNode }) {
  if (!isAuthenticated()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RoleRoute({ requireAdmin, children }: { requireAdmin: boolean; children: ReactNode }) {
  const [role, setRole] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api.me()
      .then(user => setRole(user.role || 'user'))
      .catch(() => {
        clearToken();
        setFailed(true);
      });
  }, []);

  if (failed) return <Navigate to="/login" replace />;
  if (!role) return <div className="h-screen bg-bg text-accent/50 p-2">正在加载会话...</div>;
  if (requireAdmin && role !== 'admin') return <Navigate to="/" replace />;
  if (!requireAdmin && role === 'admin') return <Navigate to="/admin" replace />;
  return <>{children}</>;
}

class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center h-screen bg-bg text-accent">
          <div className="text-center max-w-md p-6">
            <h1 className="text-xl font-bold mb-4 text-negative">系统错误</h1>
            <p className="text-sm text-accent/70 mb-4">
              {this.state.error?.message || '发生意外错误'}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.href = '/';
              }}
              className="px-4 py-2 bg-accent text-black text-sm font-bold cursor-pointer"
            >
              重新加载
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <RoleRoute requireAdmin>
                <AdminLayout />
              </RoleRoute>
            </ProtectedRoute>
          }
        >
          <Route index element={<AdminDashboard />} />
        </Route>
        <Route element={<ProtectedRoute><RoleRoute requireAdmin={false}><Layout /></RoleRoute></ProtectedRoute>}>
          <Route index element={<Dashboard />} />
          <Route path="news" element={<News />} />
          <Route path="runs" element={<Runs />} />
          <Route path="config" element={<Config />} />
          <Route path="usage" element={<Usage />} />
          <Route path="logs" element={<Logs />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}
