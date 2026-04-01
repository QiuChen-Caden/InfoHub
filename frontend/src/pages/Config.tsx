import { useEffect, useState } from 'react';
import { api } from '../api';
import type { ConfigData } from '../types';

export default function Config() {
  const [cfg, setCfg] = useState<ConfigData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.config().then(setCfg).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="text-red-400">Error: {error}</p>;
  if (!cfg) return <p className="text-muted">Loading...</p>;

  const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
    <div className="bg-card border border-border rounded-lg p-4">
      <h3 className="text-sm font-semibold text-accent mb-3">{title}</h3>
      {children}
    </div>
  );

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Configuration</h2>

      <div className="grid md:grid-cols-2 gap-4">
        <Section title="Monitored Platforms">
          <div className="flex flex-wrap gap-2">
            {cfg.platforms.map((p) => (
              <span key={p} className="px-2 py-1 bg-accent/10 text-accent text-xs rounded">
                {p}
              </span>
            ))}
          </div>
        </Section>

        <Section title="Interest Tags">
          <div className="flex flex-wrap gap-2">
            {cfg.interests.map((t) => (
              <span key={t} className="px-2 py-1 bg-green-900/30 text-green-400 text-xs rounded">
                {t}
              </span>
            ))}
          </div>
        </Section>

        <Section title="AI Configuration">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <dt className="text-muted">Model</dt><dd>{cfg.ai.model}</dd>
            <dt className="text-muted">Timeout</dt><dd>{cfg.ai.timeout}s</dd>
            <dt className="text-muted">Max Tokens</dt><dd>{cfg.ai.max_tokens}</dd>
            <dt className="text-muted">Batch Size</dt><dd>{cfg.ai.batch_size}</dd>
            <dt className="text-muted">Min Score</dt><dd>{cfg.ai.min_score}</dd>
            <dt className="text-muted">Summary</dt><dd>{cfg.ai.summary_enabled ? 'Enabled' : 'Disabled'}</dd>
          </dl>
        </Section>

        <Section title="Notification Channels">
          {cfg.notification.channels.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {cfg.notification.channels.map((c) => (
                <span key={c} className="px-2 py-1 bg-yellow-900/30 text-yellow-400 text-xs rounded">
                  {c}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-muted text-sm">No channels configured</p>
          )}
        </Section>

        <Section title="Schedule">
          <p className="text-sm font-mono">{cfg.cron_schedule}</p>
        </Section>
      </div>
    </div>
  );
}
