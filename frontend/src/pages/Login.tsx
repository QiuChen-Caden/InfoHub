import { useState } from 'react';
import { useNavigate } from 'react-router';
import { api } from '../api';
import { setToken } from '../auth';

export default function Login() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = mode === 'login'
        ? await api.login({ email, password })
        : await api.register({ name, email, password });
      setToken(res.access_token);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const inp = 'w-full bg-black border border-border text-accent text-xs px-3 py-2 focus:border-accent focus:outline-none';

  return (
    <div className="flex items-center justify-center h-screen bg-bg">
      <div className="w-full max-w-sm">
        <div className="bb-panel">
          <div className="bb-panel-header flex items-center justify-between">
            <span>{mode === 'login' ? 'LOGIN' : 'REGISTER'}</span>
            <span className="text-accent/40 text-[9px] font-normal">INFOHUB TERMINAL</span>
          </div>
          <div className="bb-panel-body">
            <form onSubmit={submit} className="space-y-3">
              {mode === 'register' && (
                <div>
                  <label className="block text-xs text-accent/70 mb-1">NAME</label>
                  <input className={inp} value={name} onChange={e => setName(e.target.value)} required />
                </div>
              )}
              <div>
                <label className="block text-xs text-accent/70 mb-1">EMAIL</label>
                <input type="email" className={inp} value={email} onChange={e => setEmail(e.target.value)} required />
              </div>
              <div>
                <label className="block text-xs text-accent/70 mb-1">PASSWORD</label>
                <input type="password" className={inp} value={password} onChange={e => setPassword(e.target.value)} required minLength={8} />
              </div>
              {error && <p className="text-negative text-xs">ERR: {error}</p>}
              <button
                type="submit"
                disabled={loading}
                className="w-full px-3 py-2 text-xs font-bold bg-accent text-black hover:bg-accent/80 disabled:opacity-50"
              >
                {loading ? 'PROCESSING...' : mode === 'login' ? '[ LOGIN ]' : '[ REGISTER ]'}
              </button>
            </form>
            <div className="mt-3 text-center">
              <button
                onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}
                className="text-xs text-link hover:text-accent cursor-pointer"
              >
                {mode === 'login' ? 'NO ACCOUNT? REGISTER' : 'HAVE ACCOUNT? LOGIN'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}