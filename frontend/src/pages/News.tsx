import { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import type { NewsItem } from '../types';
import NewsTable from '../components/NewsTable';

const PAGE_SIZE = 50;

export default function News() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [offset, setOffset] = useState(0);
  const [sourceType, setSourceType] = useState('');
  const [source, setSource] = useState('');
  const [tag, setTag] = useState('');
  const [minScore, setMinScore] = useState('');
  const [maxScore, setMaxScore] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [sources, setSources] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.newsSources().then(setSources).catch(() => {}); }, []);

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    api
      .news({
        limit: PAGE_SIZE,
        offset,
        source_type: sourceType || undefined,
        source: source || undefined,
        tag: tag || undefined,
        min_score: minScore ? Number(minScore) : undefined,
        max_score: maxScore ? Number(maxScore) : undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      })
      .then(setItems)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [offset, sourceType, source, tag, minScore, maxScore, startDate, endDate]);

  useEffect(() => { load(); }, [load]);

  const resetAndSearch = () => { setOffset(0); };

  const clearFilters = () => {
    setSourceType(''); setSource(''); setTag('');
    setMinScore(''); setMaxScore('');
    setStartDate(''); setEndDate('');
    setOffset(0);
  };

  const inputCls = "bg-black border border-border px-2 py-1 text-xs text-accent";

  return (
    <div className="space-y-2">
      <div className="bb-panel">
        <div className="bb-panel-header">NEWS FILTER</div>
        <div className="bb-panel-body flex flex-wrap gap-x-3 gap-y-2 items-end">
          <div>
            <label className="block text-xs text-accent/70 mb-0.5">SOURCE</label>
            <select value={source} onChange={(e) => { setSource(e.target.value); resetAndSearch(); }} className={inputCls}>
              <option value="">ALL</option>
              {sources.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-accent/70 mb-0.5">TYPE</label>
            <select value={sourceType} onChange={(e) => { setSourceType(e.target.value); resetAndSearch(); }} className={inputCls}>
              <option value="">ALL</option>
              <option value="hotlist">HOTLIST</option>
              <option value="rss">RSS</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-accent/70 mb-0.5">SCORE</label>
            <div className="flex items-center gap-1">
              <input type="number" step="0.1" min="0" max="1" placeholder="min"
                value={minScore} onChange={(e) => setMinScore(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && resetAndSearch()}
                className={`${inputCls} w-16`} />
              <span className="text-accent/50 text-xs">–</span>
              <input type="number" step="0.1" min="0" max="1" placeholder="max"
                value={maxScore} onChange={(e) => setMaxScore(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && resetAndSearch()}
                className={`${inputCls} w-16`} />
            </div>
          </div>
          <div>
            <label className="block text-xs text-accent/70 mb-0.5">TAG</label>
            <input type="text" value={tag} onChange={(e) => setTag(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && resetAndSearch()}
              placeholder="search tags..." className={`${inputCls} w-36`} />
          </div>
          <div>
            <label className="block text-xs text-accent/70 mb-0.5">TIME</label>
            <div className="flex items-center gap-1">
              <input type="date" value={startDate}
                onChange={(e) => { setStartDate(e.target.value); resetAndSearch(); }}
                className={inputCls} />
              <span className="text-accent/50 text-xs">–</span>
              <input type="date" value={endDate}
                onChange={(e) => { setEndDate(e.target.value); resetAndSearch(); }}
                className={inputCls} />
            </div>
          </div>
          <button onClick={() => { setOffset(0); load(); }}
            className="px-3 py-1 bg-accent text-black text-xs font-bold hover:bg-accent/80 transition-colors">
            [ SEARCH ]
          </button>
          <button onClick={clearFilters}
            className="px-3 py-1 border border-border text-accent/70 text-xs hover:text-accent hover:border-accent transition-colors">
            [ CLEAR ]
          </button>
        </div>
      </div>

      {error && <p className="text-negative text-xs">ERR: {error}</p>}
      {loading && <p className="text-accent/50 text-xs">LOADING...</p>}

      <div className="bb-panel">
        <div className="bb-panel-header">NEWS FEED</div>
        <div className="bb-panel-body">
          <NewsTable items={items} />
        </div>
      </div>

      <div className="flex gap-2 items-center text-xs">
        <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          className="px-2 py-1 border border-border text-accent disabled:opacity-30 hover:bg-accent/10">
          &lt; PREV
        </button>
        <span className="text-accent/50">{offset + 1}–{offset + items.length}</span>
        <button disabled={items.length < PAGE_SIZE} onClick={() => setOffset(offset + PAGE_SIZE)}
          className="px-2 py-1 border border-border text-accent disabled:opacity-30 hover:bg-accent/10">
          NEXT &gt;
        </button>
      </div>
    </div>
  );
}