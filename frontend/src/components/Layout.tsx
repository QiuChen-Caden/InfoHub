import { NavLink, Outlet } from 'react-router';

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/news', label: 'News' },
  { to: '/runs', label: 'Runs' },
  { to: '/config', label: 'Config' },
  { to: '/usage', label: 'Usage' },
];

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-card border-r border-border flex flex-col">
        <div className="p-4 border-b border-border">
          <h1 className="text-xl font-bold text-accent">InfoHub</h1>
          <p className="text-xs text-muted mt-1">News Intelligence</p>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === '/'}
              className={({ isActive }) =>
                `block px-3 py-2 rounded text-sm transition-colors ${
                  isActive
                    ? 'bg-accent/15 text-accent'
                    : 'text-muted hover:text-text hover:bg-white/5'
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
