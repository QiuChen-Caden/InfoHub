import { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import type { ConfigData, ConfigUpdateRequest, RSSHubFeed, ExternalFeed } from '../types';

const ALL_PLATFORMS = [
  'toutiao', 'baidu', 'wallstreetcn-hot', 'thepaper', 'bilibili-hot-search',
  'cls-hot', 'ifeng', 'tieba', 'weibo', 'douyin', 'zhihu',
];

const CRON_PRESETS = [
  { label: '每 15 分钟', value: '*/15 * * * *' },
  { label: '每 30 分钟', value: '*/30 * * * *' },
  { label: '每小时', value: '0 * * * *' },
  { label: '每 2 小时', value: '0 */2 * * *' },
  { label: '每 6 小时', value: '0 */6 * * *' },
  { label: '每天 8/12/18 点', value: '0 8,12,18 * * *' },
  { label: '每天 9 点', value: '0 9 * * *' },
  { label: '工作日 9 点', value: '0 9 * * 1-5' },
];

function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

function emptyForm(): ConfigUpdateRequest {
  return {
    platforms: [],
    interests: [],
    ai: { model: '', api_key: '', api_base: '', timeout: 120, max_tokens: 5000, batch_size: 200, batch_interval: 2, min_score: 0.7, summary_enabled: true },
    notification: { batch_interval: 2, telegram_bot_token: '', telegram_chat_id: '', feishu_webhook_url: '', dingtalk_webhook_url: '', email_from: '', email_password: '', email_to: '', slack_webhook_url: '' },
    sources: { rsshub_feeds: [], external_feeds: [] },
    cron_schedule: '', rsshub_url: '', miniflux_url: '', obsidian_vault_path: '',
  };
}

function configToForm(cfg: ConfigData): ConfigUpdateRequest {
  return {
    platforms: [...cfg.platforms],
    interests: [...cfg.interests],
    ai: { ...cfg.ai, api_key: '' },
    notification: {
      batch_interval: cfg.notification.batch_interval,
      telegram_bot_token: '', telegram_chat_id: '',
      feishu_webhook_url: '', dingtalk_webhook_url: '',
      email_from: cfg.notification.email_from, email_password: '',
      email_to: cfg.notification.email_to, slack_webhook_url: '',
    },
    sources: deepClone(cfg.sources),
    cron_schedule: cfg.cron_schedule,
    rsshub_url: cfg.rsshub_url,
    miniflux_url: cfg.miniflux_url,
    obsidian_vault_path: cfg.obsidian_vault_path,
  };
}

export default function Config() {
  const [original, setOriginal] = useState<ConfigData | null>(null);
  const [form, setForm] = useState<ConfigUpdateRequest>(emptyForm());
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [newTag, setNewTag] = useState('');
  const [configSecret, setConfigSecret] = useState('');

  const load = useCallback(() => {
    api.config().then((cfg) => {
      setOriginal(cfg);
      setForm(configToForm(cfg));
      setError('');
    }).catch((e) => setError(e.message));
  }, []);

  useEffect(() => { load(); }, [load]);

  const dirty = original ? JSON.stringify(form) !== JSON.stringify(configToForm(original)) : false;

  const save = async () => {
    setSaving(true);
    setMsg(null);
    try {
      await api.saveConfig(form, configSecret);
      setMsg({ text: 'CONFIG SAVED', ok: true });
      load();
    } catch (e: unknown) {
      setMsg({ text: (e as Error).message, ok: false });
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => {
    if (original) setForm(configToForm(original));
    setMsg(null);
  };

  if (error) return <p className="text-negative">ERR: {error}</p>;
  if (!original) return <p className="text-accent/50">LOADING...</p>;

  const togglePlatform = (p: string) => {
    setForm(f => ({
      ...f,
      platforms: f.platforms.includes(p) ? f.platforms.filter(x => x !== p) : [...f.platforms, p],
    }));
  };

  const moveTag = (i: number, dir: -1 | 1) => {
    const tags = [...form.interests];
    const j = i + dir;
    if (j < 0 || j >= tags.length) return;
    [tags[i], tags[j]] = [tags[j], tags[i]];
    setForm(f => ({ ...f, interests: tags }));
  };

  const addTag = () => {
    const t = newTag.trim();
    if (!t || form.interests.includes(t)) return;
    setForm(f => ({ ...f, interests: [...f.interests, t] }));
    setNewTag('');
  };

  const removeTag = (i: number) => {
    setForm(f => ({ ...f, interests: f.interests.filter((_, idx) => idx !== i) }));
  };

  const updateAI = (key: string, val: string | number | boolean) => {
    setForm(f => ({ ...f, ai: { ...f.ai, [key]: val } }));
  };

  const updateNotif = (key: string, val: string | number) => {
    setForm(f => ({ ...f, notification: { ...f.notification, [key]: val } }));
  };

  const updateRSSHub = (i: number, key: keyof RSSHubFeed, val: string) => {
    const feeds = deepClone(form.sources.rsshub_feeds);
    feeds[i][key] = val;
    setForm(f => ({ ...f, sources: { ...f.sources, rsshub_feeds: feeds } }));
  };

  const updateExternal = (i: number, key: keyof ExternalFeed, val: string) => {
    const feeds = deepClone(form.sources.external_feeds);
    feeds[i][key] = val;
    setForm(f => ({ ...f, sources: { ...f.sources, external_feeds: feeds } }));
  };

  const inp = "bg-black border border-border text-accent text-xs px-2 py-1 w-full focus:border-accent focus:outline-none";
  const lbl = "text-accent/70 text-xs w-32 shrink-0";

  return (
    <div className="space-y-2 pb-16">
      {/* PLATFORMS */}
      <div className="bb-panel">
        <div className="bb-panel-header">PLATFORMS</div>
        <div className="bb-panel-body flex flex-wrap gap-1">
          {ALL_PLATFORMS.map(p => (
            <button key={p} onClick={() => togglePlatform(p)}
              className={`px-2 py-0.5 text-xs border cursor-pointer ${
                form.platforms.includes(p)
                  ? 'bg-accent text-black border-accent font-bold'
                  : 'border-border text-accent/40 hover:border-accent/60'
              }`}>
              [ {p.toUpperCase()} ]
            </button>
          ))}
        </div>
      </div>

      {/* INTEREST TAGS */}
      <div className="bb-panel">
        <div className="bb-panel-header">INTEREST TAGS</div>
        <div className="bb-panel-body space-y-1">
          <div className="flex flex-wrap gap-1">
            {form.interests.map((t, i) => (
              <span key={i} className="inline-flex items-center gap-1 px-1 py-0.5 border border-positive text-positive text-xs">
                <button onClick={() => moveTag(i, -1)} className="hover:text-accent cursor-pointer" title="Move up">&uarr;</button>
                <button onClick={() => moveTag(i, 1)} className="hover:text-accent cursor-pointer" title="Move down">&darr;</button>
                {t}
                <button onClick={() => removeTag(i)} className="text-negative hover:text-red-400 cursor-pointer">&times;</button>
              </span>
            ))}
          </div>
          <div className="flex gap-1">
            <input className={inp} value={newTag} onChange={e => setNewTag(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addTag()} placeholder="Add tag..." />
            <button onClick={addTag} className="px-2 py-1 border border-positive text-positive text-xs hover:bg-positive/20 cursor-pointer">ADD</button>
          </div>
        </div>
      </div>

      {/* AI CONFIGURATION */}
      <div className="bb-panel">
        <div className="bb-panel-header">AI CONFIGURATION</div>
        <div className="bb-panel-body grid md:grid-cols-2 gap-2 text-xs">
          <div className="flex items-center gap-2"><span className={lbl}>MODEL:</span><input className={inp} value={form.ai.model} onChange={e => updateAI('model', e.target.value)} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>API_KEY:</span><input type="password" className={inp} value={form.ai.api_key} onChange={e => updateAI('api_key', e.target.value)} placeholder={original.ai.api_key} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>API_BASE:</span><input className={inp} value={form.ai.api_base} onChange={e => updateAI('api_base', e.target.value)} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>TIMEOUT:</span><input type="number" className={inp} value={form.ai.timeout} onChange={e => updateAI('timeout', Number(e.target.value))} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>MAX_TOKENS:</span><input type="number" className={inp} value={form.ai.max_tokens} onChange={e => updateAI('max_tokens', Number(e.target.value))} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>BATCH_SIZE:</span><input type="number" className={inp} value={form.ai.batch_size} onChange={e => updateAI('batch_size', Number(e.target.value))} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>BATCH_INTERVAL:</span><input type="number" className={inp} value={form.ai.batch_interval} onChange={e => updateAI('batch_interval', Number(e.target.value))} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>MIN_SCORE:</span><input type="number" step="0.1" min="0" max="1" className={inp} value={form.ai.min_score} onChange={e => updateAI('min_score', Number(e.target.value))} /></div>
          <div className="flex items-center gap-2 md:col-span-2">
            <span className={lbl}>SUMMARY:</span>
            <button onClick={() => updateAI('summary_enabled', !form.ai.summary_enabled)}
              className={`px-2 py-0.5 border text-xs cursor-pointer ${form.ai.summary_enabled ? 'border-positive text-positive' : 'border-negative text-negative'}`}>
              {form.ai.summary_enabled ? 'ENABLED' : 'DISABLED'}
            </button>
          </div>
        </div>
      </div>

      {/* NOTIFICATION CHANNELS */}
      <div className="bb-panel">
        <div className="bb-panel-header">NOTIFICATION CHANNELS</div>
        <div className="bb-panel-body space-y-2 text-xs">
          <div className="flex items-center gap-2"><span className={lbl}>BATCH_INTERVAL:</span><input type="number" className={inp} value={form.notification.batch_interval} onChange={e => updateNotif('batch_interval', Number(e.target.value))} /></div>
          <div className="border-t border-border pt-1 mt-1"><span className="text-link text-xs">TELEGRAM</span></div>
          <div className="flex items-center gap-2"><span className={lbl}>BOT_TOKEN:</span><input type="password" className={inp} value={form.notification.telegram_bot_token} onChange={e => updateNotif('telegram_bot_token', e.target.value)} placeholder={original.notification.telegram_bot_token} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>CHAT_ID:</span><input type="password" className={inp} value={form.notification.telegram_chat_id} onChange={e => updateNotif('telegram_chat_id', e.target.value)} placeholder={original.notification.telegram_chat_id} /></div>
          <div className="border-t border-border pt-1 mt-1"><span className="text-link text-xs">FEISHU</span></div>
          <div className="flex items-center gap-2"><span className={lbl}>WEBHOOK_URL:</span><input type="password" className={inp} value={form.notification.feishu_webhook_url} onChange={e => updateNotif('feishu_webhook_url', e.target.value)} placeholder={original.notification.feishu_webhook_url} /></div>
          <div className="border-t border-border pt-1 mt-1"><span className="text-link text-xs">DINGTALK</span></div>
          <div className="flex items-center gap-2"><span className={lbl}>WEBHOOK_URL:</span><input type="password" className={inp} value={form.notification.dingtalk_webhook_url} onChange={e => updateNotif('dingtalk_webhook_url', e.target.value)} placeholder={original.notification.dingtalk_webhook_url} /></div>
          <div className="border-t border-border pt-1 mt-1"><span className="text-link text-xs">EMAIL</span></div>
          <div className="flex items-center gap-2"><span className={lbl}>FROM:</span><input className={inp} value={form.notification.email_from} onChange={e => updateNotif('email_from', e.target.value)} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>PASSWORD:</span><input type="password" className={inp} value={form.notification.email_password} onChange={e => updateNotif('email_password', e.target.value)} placeholder={original.notification.email_password} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>TO:</span><input className={inp} value={form.notification.email_to} onChange={e => updateNotif('email_to', e.target.value)} /></div>
          <div className="border-t border-border pt-1 mt-1"><span className="text-link text-xs">SLACK</span></div>
          <div className="flex items-center gap-2"><span className={lbl}>WEBHOOK_URL:</span><input type="password" className={inp} value={form.notification.slack_webhook_url} onChange={e => updateNotif('slack_webhook_url', e.target.value)} placeholder={original.notification.slack_webhook_url} /></div>
        </div>
      </div>

      {/* RSS SOURCES */}
      <div className="bb-panel">
        <div className="bb-panel-header">RSS SOURCES</div>
        <div className="bb-panel-body space-y-2 text-xs">
          <div><span className="text-link">RSSHUB FEEDS</span></div>
          <table className="w-full"><thead><tr className="text-accent/70 text-left">
            <th className="px-1">ROUTE</th><th className="px-1">NAME</th><th className="px-1">CATEGORY</th><th className="w-8"></th>
          </tr></thead><tbody>
            {form.sources.rsshub_feeds.map((f, i) => (
              <tr key={i} className="border-t border-border/50">
                <td className="px-1 py-0.5"><input className={inp} value={f.route} onChange={e => updateRSSHub(i, 'route', e.target.value)} /></td>
                <td className="px-1 py-0.5"><input className={inp} value={f.name} onChange={e => updateRSSHub(i, 'name', e.target.value)} /></td>
                <td className="px-1 py-0.5"><input className={inp} value={f.category} onChange={e => updateRSSHub(i, 'category', e.target.value)} /></td>
                <td className="px-1 py-0.5"><button onClick={() => setForm(fm => ({ ...fm, sources: { ...fm.sources, rsshub_feeds: fm.sources.rsshub_feeds.filter((_, j) => j !== i) } }))} className="text-negative hover:text-red-400 cursor-pointer">&times;</button></td>
              </tr>
            ))}
          </tbody></table>
          <button onClick={() => setForm(f => ({ ...f, sources: { ...f.sources, rsshub_feeds: [...f.sources.rsshub_feeds, { route: '', name: '', category: '' }] } }))}
            className="px-2 py-0.5 border border-positive text-positive text-xs hover:bg-positive/20 cursor-pointer">+ ADD RSSHUB FEED</button>

          <div className="border-t border-border pt-2 mt-2"><span className="text-link">EXTERNAL FEEDS</span></div>
          <table className="w-full"><thead><tr className="text-accent/70 text-left">
            <th className="px-1">URL</th><th className="px-1">NAME</th><th className="px-1">CATEGORY</th><th className="w-8"></th>
          </tr></thead><tbody>
            {form.sources.external_feeds.map((f, i) => (
              <tr key={i} className="border-t border-border/50">
                <td className="px-1 py-0.5"><input className={inp} value={f.url} onChange={e => updateExternal(i, 'url', e.target.value)} /></td>
                <td className="px-1 py-0.5"><input className={inp} value={f.name} onChange={e => updateExternal(i, 'name', e.target.value)} /></td>
                <td className="px-1 py-0.5"><input className={inp} value={f.category} onChange={e => updateExternal(i, 'category', e.target.value)} /></td>
                <td className="px-1 py-0.5"><button onClick={() => setForm(fm => ({ ...fm, sources: { ...fm.sources, external_feeds: fm.sources.external_feeds.filter((_, j) => j !== i) } }))} className="text-negative hover:text-red-400 cursor-pointer">&times;</button></td>
              </tr>
            ))}
          </tbody></table>
          <button onClick={() => setForm(f => ({ ...f, sources: { ...f.sources, external_feeds: [...f.sources.external_feeds, { url: '', name: '', category: '' }] } }))}
            className="px-2 py-0.5 border border-positive text-positive text-xs hover:bg-positive/20 cursor-pointer">+ ADD EXTERNAL FEED</button>
        </div>
      </div>

      {/* SYSTEM */}
      <div className="bb-panel">
        <div className="bb-panel-header">SYSTEM</div>
        <div className="bb-panel-body space-y-2 text-xs">
          <div>
            <span className="text-accent/70 text-xs">CRON_SCHEDULE:</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {CRON_PRESETS.map(p => (
                <button key={p.value} onClick={() => setForm(f => ({ ...f, cron_schedule: p.value }))}
                  className={`px-2 py-0.5 border text-xs cursor-pointer ${
                    form.cron_schedule === p.value
                      ? 'bg-accent text-black border-accent font-bold'
                      : 'border-border text-accent/40 hover:border-accent/60'
                  }`}>
                  {p.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-accent/50 text-xs shrink-0">自定义:</span>
              <input className={inp} value={form.cron_schedule} onChange={e => setForm(f => ({ ...f, cron_schedule: e.target.value }))} placeholder="分 时 日 月 周" />
            </div>
          </div>
          <div className="grid md:grid-cols-2 gap-2">
            <div className="flex items-center gap-2"><span className={lbl}>OBSIDIAN_PATH:</span><input className={inp} value={form.obsidian_vault_path} onChange={e => setForm(f => ({ ...f, obsidian_vault_path: e.target.value }))} /></div>
            <div className="flex items-center gap-2"><span className={lbl}>RSSHUB_URL:</span><input className={inp} value={form.rsshub_url} onChange={e => setForm(f => ({ ...f, rsshub_url: e.target.value }))} /></div>
            <div className="flex items-center gap-2"><span className={lbl}>MINIFLUX_URL:</span><input className={inp} value={form.miniflux_url} onChange={e => setForm(f => ({ ...f, miniflux_url: e.target.value }))} /></div>
          </div>
        </div>
      </div>

      {/* STICKY SAVE BAR */}
      {dirty && (
        <div className="fixed bottom-0 left-0 right-0 bg-card border-t border-border px-4 py-2 flex items-center gap-3 z-50">
          <span className="text-accent text-xs animate-blink">UNSAVED CHANGES</span>
          <div className="flex-1" />
          {msg && <span className={`text-xs ${msg.ok ? 'text-positive' : 'text-negative'}`}>{msg.text}</span>}
          <input type="password" value={configSecret} onChange={e => setConfigSecret(e.target.value)}
            placeholder="CONFIG_SECRET" className="bg-black border border-border text-accent text-xs px-2 py-1 w-40" />
          <button onClick={cancel} className="px-3 py-1 border border-border text-accent text-xs hover:bg-border/30 cursor-pointer">CANCEL</button>
          <button onClick={save} disabled={saving}
            className="px-3 py-1 border border-positive text-positive text-xs hover:bg-positive/20 disabled:opacity-50 cursor-pointer">
            {saving ? 'SAVING...' : '[ SAVE CONFIG ]'}
          </button>
        </div>
      )}
    </div>
  );
}
