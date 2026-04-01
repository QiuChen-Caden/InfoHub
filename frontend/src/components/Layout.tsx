import { NavLink, Outlet, useNavigate } from 'react-router';
import { useEffect, useState } from 'react';

const links = [
  { to: '/', label: 'DASH', key: 'F1', num: 1 },
  { to: '/news', label: 'NEWS', key: 'F2', num: 2 },
  { to: '/runs', label: 'RUNS', key: 'F3', num: 3 },
  { to: '/config', label: 'CONF', key: 'F4', num: 4 },
  { to: '/usage', label: 'USAGE', key: 'F5', num: 5 },
];

function UtcClock() {
  const [time, setTime] = useState('');
  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setTime(now.toISOString().slice(0, 19).replace('T', ' ') + ' UTC');
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="text-positive text-xs font-bold">{time}</span>;
}

export default function Layout() {
  const navigate = useNavigate();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const idx = ['F1','F2','F3','F4','F5'].indexOf(e.key);
      if (idx !== -1) {
        e.preventDefault();
        navigate(links[idx].to);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [navigate]);

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg">
      {/* Top command bar */}
      <header className="bg-card border-b border-border flex items-center px-2 py-1 shrink-0">
        <div className="flex items-center gap-3">
          <span className="live-dot" />
          <span className="text-accent font-bold text-sm tracking-wider">INFOHUB TERMINAL</span>
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

        <div className="ml-auto">
          <UtcClock />
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 overflow-y-auto p-2">
        <Outlet />
      </main>

      {/* Bottom status bar */}
      <footer className="bg-card border-t border-border px-2 py-0.5 flex items-center justify-between text-xs shrink-0">
        <span className="text-accent/50">INFOHUB v1.0</span>
        <span className="text-accent/50">F1-F5 NAV | ESC CANCEL</span>
        <span className="text-positive">CONNECTED</span>
      </footer>
    </div>
  );
}