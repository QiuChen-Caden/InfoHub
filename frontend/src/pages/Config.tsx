import { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import type { ConfigData, ConfigUpdateRequest, RSSHubFeed, ExternalFeed, ApiKeyItem } from '../types';

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

const TIMEZONE_PRESETS = [
  { label: '北京 (UTC+8)', value: 'Asia/Shanghai' },
  { label: '东京 (UTC+9)', value: 'Asia/Tokyo' },
  { label: '新加坡 (UTC+8)', value: 'Asia/Singapore' },
  { label: '伦敦 (UTC+0)', value: 'Europe/London' },
  { label: '纽约 (UTC-5)', value: 'America/New_York' },
  { label: '洛杉矶 (UTC-8)', value: 'America/Los_Angeles' },
];

const ALLOWED_SECRET_KEYS = [
  'ai_api_key', 'ai_api_base',
  'miniflux_api_key',
  'telegram_bot_token', 'telegram_chat_id', 'feishu_webhook_url',
  'dingtalk_webhook_url', 'email_from', 'email_password',
  'email_to', 'slack_webhook_url',
];

function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

function toForm(cfg: ConfigData): ConfigUpdateRequest {
  return {
    platforms: [...cfg.platforms],
    interests: [...cfg.interests],
    rsshub_feeds: deepClone(cfg.rsshub_feeds),
    external_feeds: deepClone(cfg.external_feeds),
    notification: { ...cfg.notification },
    ai_config: { ...cfg.ai_config },
    cron_schedule: cfg.cron_schedule,
    timezone: cfg.timezone,
    obsidian_export: cfg.obsidian_export,
  };
}

function emptyForm(): ConfigUpdateRequest {
  return {
    platforms: [], interests: [],
    rsshub_feeds: [], external_feeds: [],
    notification: {}, ai_config: {},
    cron_schedule: '', timezone: 'Asia/Shanghai', obsidian_export: false,
  };
}

export default function Config() {
  const [original, setOriginal] = useState<ConfigData | null>(null);
  const [form, setForm] = useState<ConfigUpdateRequest>(emptyForm());
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [newTag, setNewTag] = useState('');

  // Secrets state
  const [storedKeys, setStoredKeys] = useState<string[]>([]);
  const [secretKey, setSecretKey] = useState(ALLOWED_SECRET_KEYS[0]);
  const [secretVal, setSecretVal] = useState('');
  const [secretMsg, setSecretMsg] = useState('');

  // API Keys state
  const [apiKeys, setApiKeys] = useState<ApiKeyItem[]>([]);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyExpiry, setNewKeyExpiry] = useState('');
  const [createdKey, setCreatedKey] = useState('');
  const [apiKeyMsg, setApiKeyMsg] = useState('');

  // Quota token state
  const [quotaToken, setQuotaToken] = useState('');
  const [quotaMsg, setQuotaMsg] = useState('');

  const load = useCallback(() => {
    api.config().then((cfg) => {
      setOriginal(cfg);
      setForm(toForm(cfg));
      setError('');
    }).catch((e) => setError(e.message));
  }, []);

  const loadSecrets = useCallback(() => {
    api.listSecrets().then((r) => setStoredKeys(r.keys)).catch(() => {});
  }, []);

  const loadApiKeys = useCallback(() => {
    api.listApiKeys().then(setApiKeys).catch(() => {});
  }, []);

  useEffect(() => { load(); loadSecrets(); loadApiKeys(); }, [load, loadSecrets, loadApiKeys]);

  const dirty = original ? JSON.stringify(form) !== JSON.stringify(toForm(original)) : false;

  const save = async () => {
    setSaving(true); setMsg(null);
    try {
      await api.saveConfig(form);
      setMsg({ text: '配置已保存', ok: true });
      load();
    } catch (e: unknown) {
      setMsg({ text: (e as Error).message, ok: false });
    } finally { setSaving(false); }
  };

  const cancel = () => { if (original) setForm(toForm(original)); setMsg(null); };

  if (error) return <p className="text-negative">错误: {error}</p>;
  if (!original) return <p className="text-accent/50">加载中...</p>;

  const togglePlatform = (p: string) => {
    setForm(f => ({
      ...f,
      platforms: f.platforms!.includes(p) ? f.platforms!.filter(x => x !== p) : [...f.platforms!, p],
    }));
  };

  const addTag = () => {
    const t = newTag.trim();
    if (!t || form.interests!.includes(t)) return;
    setForm(f => ({ ...f, interests: [...f.interests!, t] }));
    setNewTag('');
  };

  const removeTag = (i: number) => {
    setForm(f => ({ ...f, interests: f.interests!.filter((_, idx) => idx !== i) }));
  };

  const moveTag = (i: number, dir: -1 | 1) => {
    const tags = [...form.interests!];
    const j = i + dir;
    if (j < 0 || j >= tags.length) return;
    [tags[i], tags[j]] = [tags[j], tags[i]];
    setForm(f => ({ ...f, interests: tags }));
  };

  const updateAI = (key: string, val: unknown) => {
    setForm(f => ({ ...f, ai_config: { ...f.ai_config, [key]: val } }));
  };

  const updateNotif = (key: string, val: unknown) => {
    setForm(f => ({ ...f, notification: { ...f.notification, [key]: val } }));
  };

  const updateRSSHub = (i: number, key: keyof RSSHubFeed, val: string) => {
    const feeds = deepClone(form.rsshub_feeds!);
    feeds[i][key] = val;
    setForm(f => ({ ...f, rsshub_feeds: feeds }));
  };

  const updateExternal = (i: number, key: keyof ExternalFeed, val: string) => {
    const feeds = deepClone(form.external_feeds!);
    feeds[i][key] = val;
    setForm(f => ({ ...f, external_feeds: feeds }));
  };

  const storeSecret = async () => {
    if (!secretVal) return;
    try {
      await api.storeSecret(secretKey, secretVal);
      setSecretMsg(`${secretKey} 已保存`);
      setSecretVal('');
      loadSecrets();
    } catch (e: unknown) { setSecretMsg((e as Error).message); }
  };

  const deleteSecret = async (k: string) => {
    try {
      await api.deleteSecret(k);
      loadSecrets();
    } catch (e: unknown) { setSecretMsg((e as Error).message); }
  };

  const redeemQuotaToken = async () => {
    const token = quotaToken.trim();
    if (!token) return;
    try {
      const result = await api.redeemQuotaToken(token);
      setQuotaToken('');
      setQuotaMsg(`令牌已兑换: ${result.plan}`);
    } catch (e: unknown) {
      setQuotaMsg((e as Error).message);
    }
  };

  const inp = "bg-card border border-border text-text text-xs px-2 py-1 w-full focus:border-accent focus:outline-none";
  const lbl = "text-accent/70 text-xs w-32 shrink-0";
  const ai = form.ai_config as Record<string, unknown> ?? {};
  const notif = form.notification as Record<string, unknown> ?? {};

  return (
    <div className="space-y-2 pb-4">
      {/* TOP SAVE BAR - always visible */}
      <div className="bb-panel">
        <div className="bb-panel-body flex items-center gap-3 py-1">
          {dirty ? (
            <span className="text-accent text-xs animate-blink">● 有未保存更改</span>
          ) : (
            <span className="text-positive text-xs">● 配置已同步</span>
          )}
          <div className="flex-1" />
          {msg && <span className={`text-xs ${msg.ok ? 'text-positive' : 'text-negative'}`}>{msg.text}</span>}
          <button onClick={cancel} className="px-3 py-1 border border-border text-accent text-xs hover:bg-border/30 cursor-pointer">取消</button>
          <button onClick={save} disabled={saving}
            className="px-3 py-1 bg-accent text-black text-xs font-bold hover:bg-accent/80 disabled:opacity-30 cursor-pointer">
            {saving ? '保存中...' : '[ 保存配置 ]'}
          </button>
        </div>
      </div>

      {/* QUOTA TOKEN */}
      <div className="bb-panel">
        <div className="bb-panel-header">额度令牌</div>
        <div className="bb-panel-body text-xs space-y-1">
          <div className="flex gap-2">
            <input
              type="password"
              className={inp}
              value={quotaToken}
              onChange={e => setQuotaToken(e.target.value)}
              placeholder="ihq_..."
            />
            <button
              onClick={redeemQuotaToken}
              disabled={!quotaToken.trim()}
              className="px-3 py-1 border border-positive text-positive hover:bg-positive/20 disabled:opacity-30 cursor-pointer shrink-0"
            >
              兑换
            </button>
          </div>
          {quotaMsg && <span className="text-accent">{quotaMsg}</span>}
        </div>
      </div>

      {/* PLATFORMS */}
      <div className="bb-panel">
        <div className="bb-panel-header">平台</div>
        <div className="bb-panel-body flex flex-wrap gap-1">
          {ALL_PLATFORMS.map(p => (
            <button key={p} onClick={() => togglePlatform(p)}
              className={`px-2 py-0.5 text-xs border cursor-pointer ${
                form.platforms!.includes(p)
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
        <div className="bb-panel-header">兴趣标签</div>
        <div className="bb-panel-body space-y-1">
          <div className="flex flex-wrap gap-1">
            {form.interests!.map((t, i) => (
              <span key={i} className="inline-flex items-center gap-1 px-1 py-0.5 border border-positive text-positive text-xs">
                <button onClick={() => moveTag(i, -1)} className="hover:text-accent cursor-pointer" title="上移">&uarr;</button>
                <button onClick={() => moveTag(i, 1)} className="hover:text-accent cursor-pointer" title="下移">&darr;</button>
                {t}
                <button onClick={() => removeTag(i)} className="text-negative hover:text-red-400 cursor-pointer">&times;</button>
              </span>
            ))}
          </div>
          <div className="flex gap-1">
            <input className={inp} value={newTag} onChange={e => setNewTag(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addTag()} placeholder="添加标签..." />
            <button onClick={addTag} className="px-2 py-1 border border-positive text-positive text-xs hover:bg-positive/20 cursor-pointer">添加</button>
          </div>
        </div>
      </div>

      {/* AI CONFIGURATION */}
      <div className="bb-panel">
        <div className="bb-panel-header">AI 配置</div>
        <div className="bb-panel-body grid md:grid-cols-2 gap-2 text-xs">
          <div className="flex items-center gap-2"><span className={lbl}>模型:</span><input className={inp} value={String(ai.model ?? '')} onChange={e => updateAI('model', e.target.value)} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>超时:</span><input type="number" className={inp} value={String(ai.timeout ?? 120)} onChange={e => updateAI('timeout', Number(e.target.value))} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>最大Token:</span><input type="number" className={inp} value={String(ai.max_tokens ?? 5000)} onChange={e => updateAI('max_tokens', Number(e.target.value))} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>批大小:</span><input type="number" className={inp} value={String(ai.batch_size ?? 200)} onChange={e => updateAI('batch_size', Number(e.target.value))} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>批间隔:</span><input type="number" className={inp} value={String(ai.batch_interval ?? 2)} onChange={e => updateAI('batch_interval', Number(e.target.value))} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>最低评分:</span><input type="number" step="0.1" min="0" max="1" className={inp} value={String(ai.min_score ?? 0.7)} onChange={e => updateAI('min_score', Number(e.target.value))} /></div>
          <div className="flex items-center gap-2 md:col-span-2">
            <span className={lbl}>摘要:</span>
            <button onClick={() => updateAI('summary_enabled', !(ai.summary_enabled ?? true))}
              className={`px-2 py-0.5 border text-xs cursor-pointer ${(ai.summary_enabled ?? true) ? 'border-positive text-positive' : 'border-negative text-negative'}`}>
              {(ai.summary_enabled ?? true) ? '已启用' : '已禁用'}
            </button>
          </div>
        </div>
      </div>

      {/* NOTIFICATION CHANNELS */}
      <div className="bb-panel">
        <div className="bb-panel-header">通知渠道</div>
        <div className="bb-panel-body space-y-2 text-xs">
          <div className="flex items-center gap-2"><span className={lbl}>批间隔:</span><input type="number" className={inp} value={String(notif.batch_interval ?? 2)} onChange={e => updateNotif('batch_interval', Number(e.target.value))} /></div>
          <div className="border-t border-border pt-1 mt-1"><span className="text-link text-xs">TELEGRAM</span></div>
          <div className="flex items-center gap-2"><span className={lbl}>机器人Token:</span><input type="password" className={inp} value={String(notif.telegram_bot_token ?? '')} onChange={e => updateNotif('telegram_bot_token', e.target.value)} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>群组ID:</span><input type="password" className={inp} value={String(notif.telegram_chat_id ?? '')} onChange={e => updateNotif('telegram_chat_id', e.target.value)} /></div>
          <div className="border-t border-border pt-1 mt-1"><span className="text-link text-xs">FEISHU</span></div>
          <div className="flex items-center gap-2"><span className={lbl}>Webhook地址:</span><input type="password" className={inp} value={String(notif.feishu_webhook_url ?? '')} onChange={e => updateNotif('feishu_webhook_url', e.target.value)} /></div>
          <div className="border-t border-border pt-1 mt-1"><span className="text-link text-xs">DINGTALK</span></div>
          <div className="flex items-center gap-2"><span className={lbl}>Webhook地址:</span><input type="password" className={inp} value={String(notif.dingtalk_webhook_url ?? '')} onChange={e => updateNotif('dingtalk_webhook_url', e.target.value)} /></div>
          <div className="border-t border-border pt-1 mt-1"><span className="text-link text-xs">邮件</span></div>
          <div className="flex items-center gap-2"><span className={lbl}>发件人:</span><input className={inp} value={String(notif.email_from ?? '')} onChange={e => updateNotif('email_from', e.target.value)} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>密码:</span><input type="password" className={inp} value={String(notif.email_password ?? '')} onChange={e => updateNotif('email_password', e.target.value)} /></div>
          <div className="flex items-center gap-2"><span className={lbl}>收件人:</span><input className={inp} value={String(notif.email_to ?? '')} onChange={e => updateNotif('email_to', e.target.value)} /></div>
          <div className="border-t border-border pt-1 mt-1"><span className="text-link text-xs">SLACK</span></div>
          <div className="flex items-center gap-2"><span className={lbl}>Webhook地址:</span><input type="password" className={inp} value={String(notif.slack_webhook_url ?? '')} onChange={e => updateNotif('slack_webhook_url', e.target.value)} /></div>
        </div>
      </div>

      {/* RSS SOURCES */}
      <div className="bb-panel">
        <div className="bb-panel-header">RSS 源</div>
        <div className="bb-panel-body space-y-2 text-xs">
          <div><span className="text-link">RSSHub 订阅</span></div>
          <table className="w-full"><thead><tr className="text-accent/70 text-left">
            <th className="px-1">路由</th><th className="px-1">名称</th><th className="px-1">分类</th><th className="w-8"></th>
          </tr></thead><tbody>
            {form.rsshub_feeds!.map((f, i) => (
              <tr key={i} className="border-t border-border/50">
                <td className="px-1 py-0.5"><input className={inp} value={f.route} onChange={e => updateRSSHub(i, 'route', e.target.value)} /></td>
                <td className="px-1 py-0.5"><input className={inp} value={f.name} onChange={e => updateRSSHub(i, 'name', e.target.value)} /></td>
                <td className="px-1 py-0.5"><input className={inp} value={f.category} onChange={e => updateRSSHub(i, 'category', e.target.value)} /></td>
                <td className="px-1 py-0.5"><button onClick={() => setForm(fm => ({ ...fm, rsshub_feeds: fm.rsshub_feeds!.filter((_, j) => j !== i) }))} className="text-negative hover:text-red-400 cursor-pointer">&times;</button></td>
              </tr>
            ))}
          </tbody></table>
          <button onClick={() => setForm(f => ({ ...f, rsshub_feeds: [...f.rsshub_feeds!, { route: '', name: '', category: '' }] }))}
            className="px-2 py-0.5 border border-positive text-positive text-xs hover:bg-positive/20 cursor-pointer">+ 添加 RSSHub 订阅</button>

          <div className="border-t border-border pt-2 mt-2"><span className="text-link">外部订阅</span></div>
          <table className="w-full"><thead><tr className="text-accent/70 text-left">
            <th className="px-1">URL</th><th className="px-1">名称</th><th className="px-1">分类</th><th className="w-8"></th>
          </tr></thead><tbody>
            {form.external_feeds!.map((f, i) => (
              <tr key={i} className="border-t border-border/50">
                <td className="px-1 py-0.5"><input className={inp} value={f.url} onChange={e => updateExternal(i, 'url', e.target.value)} /></td>
                <td className="px-1 py-0.5"><input className={inp} value={f.name} onChange={e => updateExternal(i, 'name', e.target.value)} /></td>
                <td className="px-1 py-0.5"><input className={inp} value={f.category} onChange={e => updateExternal(i, 'category', e.target.value)} /></td>
                <td className="px-1 py-0.5"><button onClick={() => setForm(fm => ({ ...fm, external_feeds: fm.external_feeds!.filter((_, j) => j !== i) }))} className="text-negative hover:text-red-400 cursor-pointer">&times;</button></td>
              </tr>
            ))}
          </tbody></table>
          <button onClick={() => setForm(f => ({ ...f, external_feeds: [...f.external_feeds!, { url: '', name: '', category: '' }] }))}
            className="px-2 py-0.5 border border-positive text-positive text-xs hover:bg-positive/20 cursor-pointer">+ 添加外部订阅</button>
        </div>
      </div>

      {/* SYSTEM */}
      <div className="bb-panel">
        <div className="bb-panel-header">系统</div>
        <div className="bb-panel-body space-y-2 text-xs">
          <div>
            <span className="text-accent/70 text-xs">时区:</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {TIMEZONE_PRESETS.map(p => (
                <button key={p.value} onClick={() => setForm(f => ({ ...f, timezone: p.value }))}
                  className={`px-2 py-0.5 border text-xs cursor-pointer ${
                    form.timezone === p.value
                      ? 'bg-accent text-black border-accent font-bold'
                      : 'border-border text-accent/40 hover:border-accent/60'
                  }`}>
                  {p.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-accent/50 text-xs shrink-0">自定义:</span>
              <input className={inp} value={form.timezone ?? ''} onChange={e => setForm(f => ({ ...f, timezone: e.target.value }))} placeholder="Asia/Shanghai" />
            </div>
          </div>
          <div>
            <span className="text-accent/70 text-xs">定时计划:</span>
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
              <input className={inp} value={form.cron_schedule ?? ''} onChange={e => setForm(f => ({ ...f, cron_schedule: e.target.value }))} placeholder="分 时 日 月 周" />
            </div>
          </div>
        </div>
      </div>

      {/* SECRETS */}
      <div className="bb-panel">
        <div className="bb-panel-header">密钥</div>
        <div className="bb-panel-body space-y-2 text-xs">
          {storedKeys.length > 0 && (
            <div className="space-y-1">
              <span className="text-accent/70">已存密钥:</span>
              {storedKeys.map(k => (
                <div key={k} className="flex items-center justify-between border-b border-border/30 py-0.5">
                  <span className="text-positive">{k}</span>
                  <button onClick={() => deleteSecret(k)} className="text-negative text-xs hover:text-red-400 cursor-pointer">删除</button>
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <label className="block text-accent/70 mb-0.5">键</label>
              <select className={inp} value={secretKey} onChange={e => setSecretKey(e.target.value)}>
                {ALLOWED_SECRET_KEYS.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-accent/70 mb-0.5">值</label>
              <input type="password" className={inp} value={secretVal} onChange={e => setSecretVal(e.target.value)} />
            </div>
            <button onClick={storeSecret} className="px-2 py-1 border border-positive text-positive hover:bg-positive/20 cursor-pointer">保存</button>
          </div>
          {secretMsg && <span className="text-xs text-accent">{secretMsg}</span>}
        </div>
      </div>

      {/* API KEYS */}
      <div className="bb-panel">
        <div className="bb-panel-header">API 密钥</div>
        <div className="bb-panel-body space-y-2 text-xs">
          {apiKeys.length > 0 && (
            <div className="space-y-1">
              {apiKeys.map(k => (
                <div key={k.id} className="flex items-center justify-between border-b border-border/30 py-0.5">
                  <div className="flex items-center gap-3">
                    <span className={k.is_active ? 'text-positive' : 'text-accent/30 line-through'}>{k.name}</span>
                    <span className="text-accent/40">{k.prefix}***</span>
                    <span className="text-accent/40">
                      {k.expires_at ? `过期于 ${new Date(k.expires_at).toLocaleDateString()}` : '永不过期'}
                    </span>
                  </div>
                  {k.is_active && (
                    <button onClick={async () => {
                      await api.deleteApiKey(k.id);
                      loadApiKeys();
                    }} className="text-negative text-xs hover:text-red-400 cursor-pointer">撤销</button>
                  )}
                </div>
              ))}
            </div>
          )}
          {createdKey && (
            <div className="border border-positive p-2 space-y-1">
              <span className="text-positive">密钥已创建(请立即复制,仅显示一次):</span>
              <div className="flex gap-1">
                <input readOnly className={inp} value={createdKey} />
                <button onClick={() => { navigator.clipboard.writeText(createdKey); setApiKeyMsg('已复制'); }}
                  className="px-2 py-1 border border-accent text-accent hover:bg-accent/20 cursor-pointer shrink-0">复制</button>
              </div>
            </div>
          )}
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <label className="block text-accent/70 mb-0.5">名称</label>
              <input className={inp} value={newKeyName} onChange={e => setNewKeyName(e.target.value)} placeholder="my-agent" />
            </div>
            <div className="w-32">
              <label className="block text-accent/70 mb-0.5">有效天数</label>
              <input type="number" className={inp} value={newKeyExpiry} onChange={e => setNewKeyExpiry(e.target.value)} placeholder="留空=永不" />
            </div>
            <button onClick={async () => {
              if (!newKeyName.trim()) return;
              try {
                const res = await api.createApiKey(newKeyName.trim(), newKeyExpiry ? Number(newKeyExpiry) : undefined);
                setCreatedKey(res.key);
                setNewKeyName('');
                setNewKeyExpiry('');
                setApiKeyMsg('');
                loadApiKeys();
              } catch (e: unknown) { setApiKeyMsg((e as Error).message); }
            }} className="px-2 py-1 border border-positive text-positive hover:bg-positive/20 cursor-pointer">创建</button>
          </div>
          {apiKeyMsg && <span className="text-xs text-accent">{apiKeyMsg}</span>}
        </div>
      </div>
    </div>
  );
}
