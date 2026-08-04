import { NavLink, Outlet, useNavigate } from 'react-router';
import { useEffect, useState } from 'react';
import { api } from '../api';
import { clearToken } from '../auth';
import { setTimezone } from '../tz';
import type { User } from '../types';

const links = [
  { to: '/', label: '概览', key: 'F1', num: 1 },
  { to: '/news', label: '新闻', key: 'F2', num: 2 },
  { to: '/runs', label: '运行', key: 'F3', num: 3 },
  { to: '/config', label: '配置', key: 'F4', num: 4 },
  { to: '/usage', label: '用量', key: 'F5', num: 5 },
  { to: '/logs', label: '日志', key: 'F6', num: 6 },
];

function Clock() {
  const [time, setTime] = useState('');
  const [tz, setTz] = useState('Asia/Shanghai');
  useEffect(() => {
    api.config().then(cfg => {
      const tzName = cfg.timezone || 'Asia/Shanghai';
      setTz(tzName);
      setTimezone(tzName);
    }).catch(() => {});
  }, []);
  useEffect(() => {
    const tick = () => {
      const now = new Date();
      try {
        const formatted = now.toLocaleString('sv-SE', { timeZone: tz, hour12: false });
        setTime(formatted.replace('T', ' ') + ' ' + tz.split('/').pop());
      } catch {
        setTime(now.toISOString().slice(0, 19).replace('T', ' ') + ' UTC');
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [tz]);
  return <span className="text-positive text-xs font-bold">{time}</span>;
}

export default function Layout() {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [connected, setConnected] = useState(true);

  useEffect(() => {
    api.me().then(setUser).catch(() => {});

    // 定期检查 API 连通性
    const checkHealth = () => {
      fetch('/health')
        .then(r => setConnected(r.ok))
        .catch(() => setConnected(false));
    };
    checkHealth();
    const hid = setInterval(checkHealth, 30000);
    return () => clearInterval(hid);
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const idx = ['F1','F2','F3','F4','F5','F6'].indexOf(e.key);
      if (idx !== -1) {
        e.preventDefault();
        navigate(links[idx].to);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [navigate]);

  const logout = () => {
    clearToken();
    navigate('/login', { replace: true });
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg">
      {/* Top command bar */}
      <header className="bg-card border-b border-border flex items-center px-2 py-1 shrink-0">
        <div className="flex items-center gap-3">
          <span className="live-dot" />
          <span className="text-accent font-bold text-sm tracking-wider">INFOHUB 终端</span>
        </div>

        <nav className="flex items-center gap-1 ml-6">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === '/'}
              className={({ isActive }) =>
                `px-2 py-0.5 text-xs font-bold tracking-wide transition-colors ${
                  isActive
                    ? 'bg-accent text-black'
                    : 'text-accent/70 hover:text-accent hover:bg-accent/10'
                }`
              }
            >
              {l.num}) {l.label} [{l.key}]
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          {user && <span className="text-accent/60 text-xs">{user.email}</span>}
          <button onClick={logout} className="text-negative text-xs hover:text-red-400 cursor-pointer">退出</button>
          <Clock />
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 overflow-y-auto p-2">
        <Outlet />
      </main>

      {/* Bottom status bar */}
      <footer className="bg-card border-t border-border px-2 py-0.5 flex items-center justify-between text-xs shrink-0">
        <span className="text-accent/50">INFOHUB v2.0</span>
        <span className="text-accent/50">F1-F6 导航 | ESC 取消</span>
        <span className={connected ? "text-positive" : "text-negative"}>
          {connected ? "已连接" : "已断开"}
        </span>
      </footer>
    </div>
  );
}
