import { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import type { NewsItem } from '../types';
import NewsTable from '../components/NewsTable';

const PAGE_SIZE = 50;

export default function News() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [offset, setOffset] = useState(0);
  const [sourceType, setSourceType] = useState('');
  const [tag, setTag] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    api
      .news({
        limit: PAGE_SIZE,
        offset,
        source_type: sourceType || undefined,
        tag: tag || undefined,
      })
      .then(setItems)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [offset, sourceType, tag]);

  useEffect(() => { load(); }, [load]);

  const resetAndSearch = () => { setOffset(0); };

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">News</h2>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-muted mb-1">Source Type</label>
          <select
            value={sourceType}
            onChange={(e) => { setSourceType(e.target.value); resetAndSearch(); }}
            className="bg-card border border-border rounded px-3 py-1.5 text-sm text-text"
          >
            <option value="">All</option>
            <option value="hotlist">Hotlist</option>
            <option value="rss">RSS</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted mb-1">Tag</label>
          <input
            type="text"
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && resetAndSearch()}
            placeholder="Search tags..."
            className="bg-card border border-border rounded px-3 py-1.5 text-sm text-text w-48"
          />
        </div>
        <button
          onClick={() => { setOffset(0); load(); }}
          className="px-4 py-1.5 bg-accent text-white text-sm rounded hover:bg-accent/80 transition-colors"
        >
          Search
        </button>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}
      {loading && <p className="text-muted text-sm">Loading...</p>}

      <div className="bg-card border border-border rounded-lg p-4">
        <NewsTable items={items} />
      </div>

      {/* Pagination */}
      <div className="flex gap-3 items-center">
        <button
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          className="px-3 py-1 text-sm border border-border rounded disabled:opacity-30 hover:bg-white/5"
        >
          Previous
        </button>
        <span className="text-sm text-muted">
          {offset + 1}–{offset + items.length}
        </span>
        <button
          disabled={items.length < PAGE_SIZE}
          onClick={() => setOffset(offset + PAGE_SIZE)}
          className="px-3 py-1 text-sm border border-border rounded disabled:opacity-30 hover:bg-white/5"
        >
          Next
        </button>
      </div>
    </div>
  );
}
