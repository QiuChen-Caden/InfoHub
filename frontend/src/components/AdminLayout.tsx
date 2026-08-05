import { Outlet, useNavigate } from 'react-router';
import { useEffect, useState } from 'react';
import { api } from '../api';
import { clearToken } from '../auth';
import type { User } from '../types';
import ThemeToggle from './ThemeToggle';

export default function AdminLayout() {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [connected, setConnected] = useState(true);

  useEffect(() => {
    api.me().then(setUser).catch(() => {});

    const checkHealth = () => {
      fetch('/health')
        .then(r => setConnected(r.ok))
        .catch(() => setConnected(false));
    };
    checkHealth();
    const id = setInterval(checkHealth, 30000);
    return () => clearInterval(id);
  }, []);

  const logout = () => {
    clearToken();
    navigate('/login', { replace: true });
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg">
      <header className="bg-card border-b border-border flex items-center px-2 py-1 shrink-0">
        <div className="flex items-center gap-3">
          <span className="live-dot" />
          <span className="text-positive font-bold text-sm tracking-wider">INFOHUB 管理端</span>
          <span className="text-accent/40 text-xs">租户管理</span>
        </div>

        <div className="ml-auto flex items-center gap-3">
          {user && (
            <>
              <span className="text-positive text-xs font-bold">{user.role === 'admin' ? '管理员' : '用户'}</span>
              <span className="text-accent/60 text-xs">{user.email}</span>
            </>
          )}
          <ThemeToggle />
          <button onClick={logout} className="text-negative text-xs hover:text-red-400 cursor-pointer">退出</button>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto p-2">
        <Outlet />
      </main>

      <footer className="bg-card border-t border-border px-2 py-0.5 flex items-center justify-between text-xs shrink-0">
        <span className="text-accent/50">INFOHUB 管理端 v2.0</span>
        <span className="text-accent/50">仅管理员</span>
        <span className={connected ? 'text-positive' : 'text-negative'}>
          {connected ? '已连接' : '已断开'}
        </span>
      </footer>
    </div>
  );
}
