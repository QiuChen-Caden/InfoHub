import { useEffect, useState } from 'react';
import { api } from '../api';
import type { ConfigData } from '../types';

export default function Config() {
  const [cfg, setCfg] = useState<ConfigData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.config().then(setCfg).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="text-negative">ERR: {error}</p>;
  if (!cfg) return <p className="text-accent/50">LOADING...</p>;

  return (
    <div className="grid md:grid-cols-2 gap-2">
      <div className="bb-panel">
        <div className="bb-panel-header">MONITORED PLATFORMS</div>
        <div className="bb-panel-body flex flex-wrap gap-1">
          {cfg.platforms.map((p) => (
            <span key={p} className="px-1 py-0.5 border border-accent text-accent text-xs">
              [ {p.toUpperCase()} ]
            </span>
          ))}
        </div>
      </div>

      <div className="bb-panel">
        <div className="bb-panel-header">INTEREST TAGS</div>
        <div className="bb-panel-body flex flex-wrap gap-1">
          {cfg.interests.map((t) => (
            <span key={t} className="px-1 py-0.5 border border-positive text-positive text-xs">
              [ {t.toUpperCase()} ]
            </span>
          ))}
        </div>
      </div>

      <div className="bb-panel">
        <div className="bb-panel-header">AI CONFIGURATION</div>
        <div className="bb-panel-body text-xs space-y-0.5">
          <div className="flex"><span className="text-accent/70 w-28">MODEL:</span><span>{cfg.ai.model}</span></div>
          <div className="flex"><span className="text-accent/70 w-28">TIMEOUT:</span><span>{cfg.ai.timeout}s</span></div>
          <div className="flex"><span className="text-accent/70 w-28">MAX_TOKENS:</span><span>{cfg.ai.max_tokens}</span></div>
          <div className="flex"><span className="text-accent/70 w-28">BATCH_SIZE:</span><span>{cfg.ai.batch_size}</span></div>
          <div className="flex"><span className="text-accent/70 w-28">MIN_SCORE:</span><span>{cfg.ai.min_score}</span></div>
          <div className="flex"><span className="text-accent/70 w-28">SUMMARY:</span><span className={cfg.ai.summary_enabled ? 'text-positive' : 'text-negative'}>{cfg.ai.summary_enabled ? 'ENABLED' : 'DISABLED'}</span></div>
        </div>
      </div>

      <div className="bb-panel">
        <div className="bb-panel-header">NOTIFICATION CHANNELS</div>
        <div className="bb-panel-body flex flex-wrap gap-1">
          {cfg.notification.channels.length > 0 ? (
            cfg.notification.channels.map((c) => (
              <span key={c} className="px-1 py-0.5 border border-link text-link text-xs">
                [ {c.toUpperCase()} ]
              </span>
            ))
          ) : (
            <span className="text-accent/50 text-xs">NO CHANNELS</span>
          )}
        </div>
      </div>

      <div className="bb-panel md:col-span-2">
        <div className="bb-panel-header">SCHEDULE</div>
        <div className="bb-panel-body text-xs">
          <span className="text-accent/70">CRON: </span>{cfg.cron_schedule}
        </div>
      </div>
    </div>
  );
}
