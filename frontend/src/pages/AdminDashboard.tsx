import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import StatCard from '../components/StatCard';
import { formatTime } from '../tz';
import type {
  AdminOverview, AdminQuotaToken, AdminRun, AdminTaskStatus,
  AdminTenant, AdminTenantDetail, User,
} from '../types';

type Role = 'user' | 'admin';
type Plan = 'free' | 'pro' | 'enterprise';

const ADMIN_SECRET_KEYS = [
  'ai_api_key', 'ai_api_base', 'miniflux_api_key',
  'telegram_bot_token', 'telegram_chat_id', 'feishu_webhook_url',
  'dingtalk_webhook_url', 'email_from', 'email_password',
  'email_to', 'slack_webhook_url',
];

const DEFAULT_TOKEN_LIMITS = {
  ai_filter: 5000,
  ai_summary: 500,
  ai_translate: 1000,
  push_telegram: 2000,
  push_feishu: 2000,
  push_dingtalk: 2000,
  push_email: 2000,
  push_slack: 2000,
};

const selectClass = 'bg-card border border-border text-text text-xs px-2 py-1 focus:border-accent focus:outline-none';
const inputClass = 'bg-card border border-border text-text text-xs px-2 py-1 focus:border-accent focus:outline-none';
const textareaClass = 'bg-card border border-border text-text text-xs px-2 py-1 focus:border-accent focus:outline-none font-mono';
const primaryButton = 'px-2 py-1 bg-accent text-black text-xs font-bold hover:bg-accent/80 disabled:opacity-50 disabled:cursor-not-allowed';
const secondaryButton = 'px-2 py-1 border border-border text-accent/70 text-xs hover:text-accent hover:border-accent disabled:opacity-50 disabled:cursor-not-allowed';
const dangerButton = 'px-2 py-1 border border-negative text-negative text-xs hover:bg-negative/20 disabled:opacity-50 disabled:cursor-not-allowed';

function RunStatus({ run }: { run: AdminRun }) {
  if (!run.finished_at) return <span className="text-accent">运行中</span>;
  if (run.errors) return <span className="text-negative">错误</span>;
  return <span className="text-positive">成功</span>;
}

function TaskPanel({ tasks }: { tasks: AdminTaskStatus | null }) {
  return (
    <div className="bb-panel flex flex-col min-h-0">
      <div className="bb-panel-header flex items-center justify-between">
        <span>全局任务状态</span>
        {tasks && (
          <span className="text-accent/40 text-[9px] font-normal tracking-normal">
            运行中 {tasks.running_count} · 失败 {tasks.failed_count}
          </span>
        )}
      </div>
      <div className="bb-panel-body overflow-y-auto">
        {!tasks ? (
          <p className="text-accent/50">正在加载任务...</p>
        ) : (
          <table className="w-full text-xs">
            <thead className="sticky top-0">
              <tr className="bg-header-bg text-left text-accent/70 uppercase">
                <th className="px-2 py-1">运行</th>
                <th className="px-2 py-1">租户</th>
                <th className="px-2 py-1">开始时间</th>
                <th className="px-2 py-1">状态</th>
                <th className="px-2 py-1">计数</th>
                <th className="px-2 py-1">失败原因</th>
              </tr>
            </thead>
            <tbody>
              {tasks.recent_runs.map((run, index) => (
                <tr key={`${run.tenant_id}-${run.id}`} className={index % 2 === 0 ? 'bg-card' : 'bg-bg'}>
                  <td className="px-2 py-1">#{run.id}</td>
                  <td className="px-2 py-1 text-link">{run.tenant_email}</td>
                  <td className="px-2 py-1 text-accent/60">{formatTime(run.started_at)}</td>
                  <td className="px-2 py-1"><RunStatus run={run} /></td>
                  <td className="px-2 py-1 text-accent/60">
                    热{run.hotlist_count} RSS{run.rss_count} 匹{run.matched_count} 推{run.pushed_count}
                  </td>
                  <td className="px-2 py-1 text-negative max-w-[360px] truncate" title={run.errors}>
                    {run.errors || '-'}
                  </td>
                </tr>
              ))}
              {!tasks.recent_runs.length && (
                <tr>
                  <td className="px-2 py-4 text-accent/50 text-center" colSpan={6}>暂无运行</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default function AdminDashboard() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [tasks, setTasks] = useState<AdminTaskStatus | null>(null);
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [detail, setDetail] = useState<AdminTenantDetail | null>(null);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [roleDraft, setRoleDraft] = useState<Role>('user');
  const [planDraft, setPlanDraft] = useState<Plan>('free');
  const [newPassword, setNewPassword] = useState('');
  const [clearConfirm, setClearConfirm] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState('');
  const [configText, setConfigText] = useState('{}');
  const [secretKey, setSecretKey] = useState(ADMIN_SECRET_KEYS[0]);
  const [secretValue, setSecretValue] = useState('');
  const [quotaTokens, setQuotaTokens] = useState<AdminQuotaToken[]>([]);
  const [tokenPlan, setTokenPlan] = useState('custom');
  const [tokenLimits, setTokenLimits] = useState(JSON.stringify(DEFAULT_TOKEN_LIMITS, null, 2));
  const [tokenCount, setTokenCount] = useState('1');
  const [tokenExpiry, setTokenExpiry] = useState('365');
  const [generatedTokens, setGeneratedTokens] = useState<string[]>([]);

  const selectedTenant = useMemo(
    () => tenants.find(tenant => tenant.id === selectedId) || null,
    [tenants, selectedId],
  );
  const selectedIsSelf = Boolean(currentUser && selectedTenant && currentUser.id === selectedTenant.id);

  const loadAll = useCallback(() => {
    setError('');
    Promise.all([
      api.me(), api.adminOverview(), api.adminTasks(), api.adminTenants(), api.adminQuotaTokens(),
    ])
      .then(([me, overviewData, taskData, tenantRows, tokenRows]) => {
        setCurrentUser(me);
        setOverview(overviewData);
        setTasks(taskData);
        setTenants(tenantRows);
        setQuotaTokens(tokenRows);
        setSelectedId(prev => (
          prev && tenantRows.some(tenant => tenant.id === prev)
            ? prev
            : tenantRows[0]?.id || ''
        ));
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const loadDetail = useCallback((tenantId: string) => {
    if (!tenantId) {
      setDetail(null);
      return;
    }
    api.adminTenant(tenantId)
      .then(data => {
        setDetail(data);
        setRoleDraft((data.tenant.role === 'admin' ? 'admin' : 'user') as Role);
        setPlanDraft((['free', 'pro', 'enterprise'].includes(data.tenant.plan) ? data.tenant.plan : 'free') as Plan);
        setNewPassword('');
        setClearConfirm('');
        setDeleteConfirm('');
        setConfigText(JSON.stringify(data.config || {}, null, 2));
        setSecretKey(ADMIN_SECRET_KEYS[0]);
        setSecretValue('');
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);
  useEffect(() => { loadDetail(selectedId); }, [selectedId, loadDetail]);

  const refreshAfterAction = (message: string) => {
    setNotice(message);
    loadAll();
    if (selectedId) loadDetail(selectedId);
  };

  const runAction = async (fn: () => Promise<unknown>, message: string) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await fn();
      refreshAfterAction(message);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const deleteSelectedTenant = async () => {
    if (!detail) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api.adminDeleteTenant(detail.tenant.id, deleteConfirm);
      setSelectedId('');
      setDetail(null);
      setDeleteConfirm('');
      setNotice('租户已删除');
      loadAll();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const saveTenantConfig = async () => {
    if (!detail) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const parsed = JSON.parse(configText);
      const updated = await api.adminUpdateTenantConfig(detail.tenant.id, parsed);
      setDetail(updated);
      setConfigText(JSON.stringify(updated.config || {}, null, 2));
      setNotice('远程配置已保存');
      loadAll();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const saveTenantSecret = async () => {
    if (!detail || !secretValue) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api.adminSetTenantSecret(detail.tenant.id, secretKey, secretValue);
      setSecretValue('');
      setNotice('密钥已保存');
      loadDetail(detail.tenant.id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const generateQuotaTokens = async () => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const limits = JSON.parse(tokenLimits) as Record<string, number>;
      const result = await api.adminCreateQuotaTokens(
        tokenPlan.trim() || 'custom',
        limits,
        Number(tokenCount) || 1,
        tokenExpiry ? Number(tokenExpiry) : undefined,
      );
      setGeneratedTokens(result.tokens);
      setNotice(`已生成 ${result.tokens.length} 个额度令牌`);
      loadAll();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const deleteTenantSecret = async (keyName: string) => {
    if (!detail) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api.adminDeleteTenantSecret(detail.tenant.id, keyName);
      setNotice('密钥已删除');
      loadDetail(detail.tenant.id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const config = detail?.config || {};
  const configList = [
    ['定时', String(config.cron_schedule || '-')],
    ['时区', String(config.timezone || '-')],
    ['平台', String((config.platforms as unknown[] | undefined)?.length ?? 0)],
    ['兴趣', String((config.interests as unknown[] | undefined)?.length ?? 0)],
    ['RSSHub', String((config.rsshub_feeds as unknown[] | undefined)?.length ?? 0)],
    ['外部RSS', String((config.external_feeds as unknown[] | undefined)?.length ?? 0)],
    ['OBSIDIAN', config.obsidian_export ? '开' : '关'],
  ];

  if (error && !overview) return <p className="text-negative">错误: {error}</p>;
  if (!overview) return <p className="text-accent/50">正在加载管理控制台...</p>;

  return (
    <div className="flex flex-col gap-2 h-full">
      <div className="grid grid-cols-7 gap-2 shrink-0">
        <StatCard label="租户数" value={overview.total_tenants} sub={`${overview.active_tenants} 活跃`} />
        <StatCard label="管理员" value={overview.admin_tenants} />
        <StatCard label="新闻总数" value={overview.total_news} />
        <StatCard label="热榜" value={overview.hotlist_total} />
        <StatCard label="RSS" value={overview.rss_total} />
        <StatCard label="运行" value={overview.total_runs} />
        <StatCard label="最近运行" value={formatTime(overview.latest_run)} />
      </div>

      {(error || notice) && (
        <div className={`border px-2 py-1 text-xs ${error ? 'border-negative text-negative' : 'border-positive text-positive'}`}>
          {error ? `错误: ${error}` : notice}
        </div>
      )}

      <div className="bb-panel shrink-0">
        <div className="bb-panel-header flex items-center justify-between">
          <span>额度令牌</span>
          <span className="text-accent/40 text-[9px] font-normal tracking-normal">
            {quotaTokens.filter(token => token.is_active).length} 个可用
          </span>
        </div>
        <div className="bb-panel-body grid grid-cols-[180px_90px_110px_1fr_auto] gap-2 items-end text-xs">
          <label>
            <span className="block text-accent/50 mb-1">套餐标识</span>
            <input className={`${inputClass} w-full`} value={tokenPlan} onChange={e => setTokenPlan(e.target.value)} />
          </label>
          <label>
            <span className="block text-accent/50 mb-1">数量</span>
            <input type="number" min="1" max="100" className={`${inputClass} w-full`} value={tokenCount} onChange={e => setTokenCount(e.target.value)} />
          </label>
          <label>
            <span className="block text-accent/50 mb-1">有效天数</span>
            <input type="number" min="1" className={`${inputClass} w-full`} value={tokenExpiry} onChange={e => setTokenExpiry(e.target.value)} />
          </label>
          <label>
            <span className="block text-accent/50 mb-1">月度额度 JSON</span>
            <input className={`${inputClass} w-full font-mono`} value={tokenLimits.replace(/\s+/g, ' ')} onChange={e => setTokenLimits(e.target.value)} />
          </label>
          <button className={primaryButton} disabled={busy} onClick={generateQuotaTokens}>生成</button>
        </div>
        {(generatedTokens.length > 0 || quotaTokens.length > 0) && (
          <div className="bb-panel-body border-t border-border grid grid-cols-2 gap-3 text-xs">
            <div className="space-y-1">
              {generatedTokens.length > 0 && (
                <>
                  <div className="flex items-center justify-between text-positive">
                    <span>新令牌仅显示一次</span>
                    <button className={secondaryButton} onClick={() => navigator.clipboard.writeText(generatedTokens.join('\n'))}>复制全部</button>
                  </div>
                  {generatedTokens.map(token => <div key={token} className="font-mono text-accent break-all">{token}</div>)}
                </>
              )}
            </div>
            <div className="max-h-24 overflow-y-auto space-y-1">
              {quotaTokens.slice(0, 20).map(token => (
                <div key={token.id} className="flex items-center gap-2 border-b border-border/30 py-0.5">
                  <span className="font-mono text-accent/70">{token.prefix}...</span>
                  <span>{token.plan}</span>
                  <span
                    className="max-w-[220px] truncate text-accent/50"
                    title={JSON.stringify(token.limits)}
                  >
                    {Object.entries(token.limits).map(([key, value]) => `${key}:${value}`).join(' ')}
                  </span>
                  <span className={token.redeemed_by ? 'text-accent/40' : token.is_active ? 'text-positive' : 'text-negative'}>
                    {token.redeemed_by ? '已兑换' : token.is_active ? '可用' : '已撤销'}
                  </span>
                  <span className="flex-1" />
                  {token.is_active && !token.redeemed_by && (
                    <button
                      className="text-negative"
                      onClick={() => runAction(() => api.adminRevokeQuotaToken(token.id), '令牌已撤销')}
                    >撤销</button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 min-h-[320px]">
        <div className="bb-panel flex flex-col min-h-0">
          <div className="bb-panel-header flex items-center justify-between">
            <span>租户控制</span>
            <span className="text-accent/40 text-[9px] font-normal tracking-normal">
              {tenants.length} 个账号
            </span>
          </div>
          <div className="bb-panel-body overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0">
                <tr className="bg-header-bg text-left text-accent/70 uppercase">
                  <th className="px-2 py-1">邮箱</th>
                  <th className="px-2 py-1">角色</th>
                  <th className="px-2 py-1">套餐</th>
                  <th className="px-2 py-1">状态</th>
                  <th className="px-2 py-1 text-right">新闻</th>
                  <th className="px-2 py-1 text-right">运行</th>
                  <th className="px-2 py-1">操作</th>
                </tr>
              </thead>
              <tbody>
                {tenants.map((tenant, index) => (
                  <tr key={tenant.id} className={`${index % 2 === 0 ? 'bg-card' : 'bg-bg'} ${tenant.id === selectedId ? 'outline outline-1 outline-accent' : ''}`}>
                    <td className="px-2 py-1 text-link">{tenant.email}</td>
                    <td className="px-2 py-1">
                      <span className={tenant.role === 'admin' ? 'text-positive' : 'text-accent/70'}>
                        {(tenant.role === 'admin' ? '管理员' : '用户')}
                      </span>
                    </td>
                    <td className="px-2 py-1 text-accent/70">{({free:'免费',pro:'专业',enterprise:'企业'} as Record<string,string>)[tenant.plan] || tenant.plan}</td>
                    <td className="px-2 py-1">
                      <span className={tenant.is_active ? 'text-positive' : 'text-negative'}>
                        {tenant.is_active ? '正常' : '禁用'}
                      </span>
                    </td>
                    <td className="px-2 py-1 text-right">{tenant.news_count}</td>
                    <td className="px-2 py-1 text-right">{tenant.run_count}</td>
                    <td className="px-2 py-1">
                      <button className={secondaryButton} onClick={() => setSelectedId(tenant.id)}>
                        选择
                      </button>
                    </td>
                  </tr>
                ))}
                {!tenants.length && (
                  <tr>
                    <td className="px-2 py-4 text-accent/50 text-center" colSpan={7}>暂无租户</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bb-panel flex flex-col min-h-0">
          <div className="bb-panel-header flex items-center justify-between">
            <span>租户详情</span>
            {selectedTenant && <span className="text-accent/40 text-[9px] font-normal tracking-normal">{selectedTenant.email}</span>}
          </div>
          <div className="bb-panel-body overflow-y-auto">
            {!detail ? (
              <p className="text-accent/50">选择租户</p>
            ) : (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div><span className="text-accent/50">ID:</span> <span className="text-accent/70">{detail.tenant.id}</span></div>
                  <div><span className="text-accent/50">创建时间:</span> <span>{formatTime(detail.tenant.created_at)}</span></div>
                  <div><span className="text-accent/50">名称:</span> <span>{detail.tenant.name}</span></div>
                  <div><span className="text-accent/50">最近运行:</span> <span>{formatTime(detail.tenant.latest_run)}</span></div>
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs">
                  {configList.map(([label, value]) => (
                    <div key={label} className="border border-border p-2">
                      <div className="text-accent/50">{label}</div>
                      <div className="text-accent font-bold">{value}</div>
                    </div>
                  ))}
                </div>

                <div className="border border-border p-2 space-y-2">
                  <div className="text-accent/70 font-bold">账号操作</div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      className={detail.tenant.is_active ? dangerButton : primaryButton}
                      disabled={busy || selectedIsSelf}
                      onClick={() => runAction(
                        () => api.adminSetTenantStatus(detail.tenant.id, !detail.tenant.is_active),
                        detail.tenant.is_active ? '租户已禁用' : '租户已启用',
                      )}
                    >
                      {detail.tenant.is_active ? '禁用用户' : '启用用户'}
                    </button>

                    <select className={selectClass} value={roleDraft} onChange={e => setRoleDraft(e.target.value as Role)} disabled={busy || selectedIsSelf}>
                      <option value="user">用户</option>
                      <option value="admin">管理员</option>
                    </select>
                    <button
                      className={secondaryButton}
                      disabled={busy || selectedIsSelf || roleDraft === detail.tenant.role}
                      onClick={() => runAction(
                        () => api.adminSetTenantRole(detail.tenant.id, roleDraft),
                        '角色已更新',
                      )}
                    >
                      更新角色
                    </button>

                    <select className={selectClass} value={planDraft} onChange={e => setPlanDraft(e.target.value as Plan)} disabled={busy}>
                      <option value="free">免费</option>
                      <option value="pro">专业</option>
                      <option value="enterprise">企业</option>
                    </select>
                    <button
                      className={secondaryButton}
                      disabled={busy || planDraft === detail.tenant.plan}
                      onClick={() => runAction(
                        () => api.adminSetTenantPlan(detail.tenant.id, planDraft),
                        '套餐已更新',
                      )}
                    >
                      更新套餐
                    </button>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      className={`${inputClass} w-64`}
                      type="password"
                      placeholder="新密码"
                      value={newPassword}
                      onChange={e => setNewPassword(e.target.value)}
                    />
                    <button
                      className={secondaryButton}
                      disabled={busy || newPassword.length < 8}
                      onClick={() => runAction(
                        () => api.adminResetTenantPassword(detail.tenant.id, newPassword),
                        '密码已重置',
                      )}
                    >
                      重置密码
                    </button>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      className={`${inputClass} w-72`}
                      placeholder={`输入 ${detail.tenant.email} 以清空数据`}
                      value={clearConfirm}
                      onChange={e => setClearConfirm(e.target.value)}
                    />
                    <button
                      className={dangerButton}
                      disabled={busy || clearConfirm !== detail.tenant.email}
                      onClick={() => runAction(
                        () => api.adminClearTenantData(detail.tenant.id, clearConfirm),
                        '租户数据已清空',
                      )}
                    >
                      清空用户数据
                    </button>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      className={`${inputClass} w-72`}
                      placeholder={`输入 ${detail.tenant.email} 以删除用户`}
                      value={deleteConfirm}
                      onChange={e => setDeleteConfirm(e.target.value)}
                    />
                    <button
                      className={dangerButton}
                      disabled={busy || selectedIsSelf || deleteConfirm !== detail.tenant.email}
                      onClick={deleteSelectedTenant}
                    >
                      删除用户
                    </button>
                  </div>
                  {selectedIsSelf && <div className="text-accent/50">自我保护:当前管理员无法被禁用、降级或删除。</div>}
                </div>

                <div className="border border-border p-2 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="text-accent/70 font-bold">远程配置编辑器</div>
                    <div className="text-accent/40 text-[9px]">JSON 配置 · 已屏蔽的密钥将被保留</div>
                  </div>
                  <textarea
                    className={`${textareaClass} w-full min-h-[240px]`}
                    spellCheck={false}
                    value={configText}
                    onChange={event => setConfigText(event.target.value)}
                  />
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      className={primaryButton}
                      disabled={busy}
                      onClick={saveTenantConfig}
                    >
                      保存远程配置
                    </button>
                    <button
                      className={secondaryButton}
                      disabled={busy}
                      onClick={() => setConfigText(JSON.stringify(detail.config || {}, null, 2))}
                    >
                      重置编辑器
                    </button>
                  </div>

                  <div className="border-t border-border pt-2 space-y-2">
                    <div className="text-accent/70 font-bold">远程密钥覆盖</div>
                    <div className="flex flex-wrap gap-1">
                      {(detail.stored_secret_keys || []).map(keyName => (
                        <span key={keyName} className="inline-flex items-center gap-1 border border-positive text-positive px-1 py-0.5">
                          {keyName}
                          <button
                            className="text-negative hover:text-red-400"
                            disabled={busy}
                            onClick={() => deleteTenantSecret(keyName)}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                      {!detail.stored_secret_keys?.length && <span className="text-accent/50">暂无已存密钥</span>}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <select className={selectClass} value={secretKey} onChange={event => setSecretKey(event.target.value)} disabled={busy}>
                        {ADMIN_SECRET_KEYS.map(keyName => <option key={keyName} value={keyName}>{keyName}</option>)}
                      </select>
                      <input
                        className={`${inputClass} w-72`}
                        type="password"
                        placeholder="新密钥值"
                        value={secretValue}
                        onChange={event => setSecretValue(event.target.value)}
                      />
                      <button
                        className={secondaryButton}
                        disabled={busy || !secretValue}
                        onClick={saveTenantSecret}
                      >
                        保存密钥
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 min-h-[260px]">
        <TaskPanel tasks={tasks} />

        <div className="bb-panel flex flex-col min-h-0">
          <div className="bb-panel-header">选中租户的运行</div>
          <div className="bb-panel-body overflow-y-auto">
            {!detail ? (
              <p className="text-accent/50">选择租户</p>
            ) : (
              <table className="w-full text-xs">
                <thead className="sticky top-0">
                  <tr className="bg-header-bg text-left text-accent/70 uppercase">
                    <th className="px-2 py-1">运行</th>
                    <th className="px-2 py-1">开始时间</th>
                    <th className="px-2 py-1">状态</th>
                    <th className="px-2 py-1">计数</th>
                    <th className="px-2 py-1">错误</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.recent_runs.map((run, index) => (
                    <tr key={run.id} className={index % 2 === 0 ? 'bg-card' : 'bg-bg'}>
                      <td className="px-2 py-1">#{run.id}</td>
                      <td className="px-2 py-1 text-accent/60">{formatTime(run.started_at)}</td>
                      <td className="px-2 py-1"><RunStatus run={run} /></td>
                      <td className="px-2 py-1 text-accent/60">
                        热{run.hotlist_count} RSS{run.rss_count} 新{run.new_count} 匹{run.matched_count} 推{run.pushed_count}
                      </td>
                      <td className="px-2 py-1 text-negative max-w-[420px] truncate" title={run.errors}>{run.errors || '-'}</td>
                    </tr>
                  ))}
                  {!detail.recent_runs.length && (
                    <tr>
                      <td className="px-2 py-4 text-accent/50 text-center" colSpan={5}>暂无运行</td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
