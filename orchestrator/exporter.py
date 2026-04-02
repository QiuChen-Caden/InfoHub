"""HTML 报告 + Obsidian 知识库导出"""

import logging
from html import escape
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from collections import Counter

from models import NewsItem

log = logging.getLogger("infohub.export")


class ObsidianExporter:
    """导出 Markdown 到 Obsidian 知识库 00_Inbox"""

    def __init__(self, vault_path: str):
        self.inbox = Path(vault_path) / "00_Inbox"
        self.inbox.mkdir(parents=True, exist_ok=True)

    def export(self, items: List[NewsItem], now: datetime,
               summary: str = ""):
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H-%M")
        filename = f"{date_str} - InfoHub {time_str}.md"
        filepath = self.inbox / filename

        by_tag = _group_by_tag(items)

        lines = [
            "---",
            f"date: {date_str}",
            "tags: [infohub, 日报]",
            f"source_count: {len(items)}",
            "---",
            "",
            f"# {date_str} 信息日报",
            "",
        ]

        if summary:
            lines.extend(["## AI 分析总览", "", summary, ""])

        for tag, tag_items in by_tag.items():
            lines.append(f"## {tag}")
            lines.append("")
            for it in tag_items:
                source = f"*{it.source}*"
                if it.url:
                    lines.append(
                        f"- [{it.title}]({it.url}) — {source}"
                    )
                else:
                    lines.append(f"- {it.title} — {source}")
            lines.append("")

        filepath.write_text("\n".join(lines), encoding="utf-8")
        log.info(f"Obsidian 导出: {filepath}")


def _group_by_tag(items: List[NewsItem]) -> Dict[str, List[NewsItem]]:
    by_tag: dict = {}
    for item in items:
        tag = item.tags[0] if item.tags else "其他"
        by_tag.setdefault(tag, []).append(item)
    return by_tag


class HTMLExporter:
    """生成 HTML 交互报告 — 带目录、筛选、统计卡片"""

    def __init__(self, output_dir: str, tenant_id: str = ""):
        base = Path(output_dir) / "html"
        if tenant_id:
            base = base / tenant_id
        self.output_dir = base
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, items: List[NewsItem], now: datetime,
                 summary: str = ""):
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H-%M")
        day_dir = self.output_dir / date_str
        day_dir.mkdir(exist_ok=True)
        filepath = day_dir / f"{time_str}.html"

        by_tag = _group_by_tag(items)
        sources = Counter(it.source for it in items)

        # 统计卡片
        stats = self._stats_html(items, by_tag, sources)
        # 目录导航
        nav = self._nav_html(by_tag)
        # AI 摘要
        summary_html = self._summary_html(summary)
        # 内容区
        sections = self._sections_html(by_tag)
        # 来源筛选器
        filters = self._filter_html(sources)

        html = self._template(date_str, time_str, stats, nav,
                              filters, summary_html, sections)

        filepath.write_text(html, encoding="utf-8")
        latest_dir = self.output_dir / "latest"
        latest_dir.mkdir(exist_ok=True)
        (latest_dir / "current.html").write_text(html, encoding="utf-8")
        log.info(f"HTML 报告: {filepath}")

    def _stats_html(self, items, by_tag, sources):
        hotlist = sum(1 for i in items if i.source_type == "hotlist")
        rss = sum(1 for i in items if i.source_type == "rss")
        avg_score = (sum(i.score for i in items) / len(items)
                     if items else 0)
        return f"""<div class="stats">
<div class="stat"><span class="num">{len(items)}</span><span class="label">总条数</span></div>
<div class="stat"><span class="num">{len(by_tag)}</span><span class="label">标签数</span></div>
<div class="stat"><span class="num">{hotlist}</span><span class="label">热榜</span></div>
<div class="stat"><span class="num">{rss}</span><span class="label">RSS</span></div>
<div class="stat"><span class="num">{avg_score:.0%}</span><span class="label">平均相关度</span></div>
<div class="stat"><span class="num">{len(sources)}</span><span class="label">来源数</span></div>
</div>"""

    def _nav_html(self, by_tag):
        links = " ".join(
            f'<a href="#tag-{escape(t)}" class="nav-tag">'
            f'{escape(t)} ({len(items)})</a>'
            for t, items in by_tag.items()
        )
        return f'<nav class="tag-nav">{links}</nav>'

    def _filter_html(self, sources):
        opts = "".join(
            f'<label><input type="checkbox" value="{escape(s)}" '
            f'checked onchange="filterSource()">{escape(s)} '
            f'({c})</label>'
            for s, c in sources.most_common()
        )
        return f'<div class="filters"><b>来源筛选:</b> {opts}</div>'

    def _summary_html(self, summary: str):
        if not summary:
            return ""
        return (f'<details class="summary" open>'
                f'<summary><b>AI 分析</b></summary>'
                f'<pre>{escape(summary)}</pre></details>')

    def _sections_html(self, by_tag):
        parts = []
        for tag, tag_items in by_tag.items():
            rows = ""
            for it in tag_items:
                score_pct = f'{it.score:.0%}' if it.score else '—'
                title_safe = escape(it.title)
                source_safe = escape(it.source)
                url_safe = escape(it.url) if it.url else ""
                link = (f'<a href="{url_safe}" target="_blank" '
                        f'rel="noopener">{title_safe}</a>'
                        if url_safe else title_safe)
                rows += (f'<tr data-source="{source_safe}">'
                         f'<td>{link}</td>'
                         f'<td class="src">{source_safe}</td>'
                         f'<td><span class="score">{score_pct}</span>'
                         f'</td></tr>\n')
            parts.append(
                f'<section id="tag-{escape(tag)}">'
                f'<h2>{escape(tag)} ({len(tag_items)})</h2>'
                f'<table><thead><tr>'
                f'<th>标题</th><th>来源</th><th>相关度</th>'
                f'</tr></thead><tbody>{rows}</tbody></table>'
                f'</section>'
            )
        return "\n".join(parts)

    @staticmethod
    def _template(date, time, stats, nav, filters, summary, sections):
        return f"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>InfoHub {date} {time}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,system-ui,sans-serif;max-width:1000px;
margin:0 auto;padding:20px;background:#0d1117;color:#c9d1d9}}
h1{{color:#58a6ff;margin-bottom:16px;font-size:1.5em}}
h2{{color:#8b949e;margin:20px 0 10px;border-bottom:1px solid #21262d;
padding-bottom:6px;font-size:1.1em}}
.stats{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}}
.stat{{background:#161b22;border:1px solid #21262d;border-radius:8px;
padding:12px 16px;text-align:center;flex:1;min-width:80px}}
.stat .num{{display:block;font-size:1.4em;font-weight:700;color:#58a6ff}}
.stat .label{{font-size:.75em;color:#8b949e}}
.tag-nav{{margin:12px 0;display:flex;flex-wrap:wrap;gap:6px}}
.nav-tag{{background:#21262d;color:#c9d1d9;padding:4px 10px;
border-radius:14px;font-size:.8em;text-decoration:none}}
.nav-tag:hover{{background:#30363d}}
.filters{{margin:12px 0;font-size:.8em;color:#8b949e}}
.filters label{{margin-right:10px;cursor:pointer}}
.filters input{{margin-right:3px}}
table{{width:100%;border-collapse:collapse;margin-bottom:8px}}
th,td{{padding:6px 10px;text-align:left;border-bottom:1px solid #21262d}}
th{{color:#8b949e;font-weight:600;font-size:.85em}}
td{{font-size:.9em}}
.src{{color:#8b949e;white-space:nowrap}}
a{{color:#58a6ff;text-decoration:none}}
a:hover{{text-decoration:underline}}
.score{{background:#1f6feb;color:#fff;padding:2px 8px;border-radius:10px;
font-size:.75em}}
.summary{{background:#161b22;padding:14px;border-radius:8px;margin:14px 0;
border:1px solid #21262d}}
.summary pre{{white-space:pre-wrap;line-height:1.6;margin-top:8px;
font-size:.85em}}
tr.hidden{{display:none}}
</style></head><body>
<h1>InfoHub {date} {time}</h1>
{stats}
{nav}
{filters}
{summary}
{sections}
<script>
function filterSource(){{
  const checked=new Set();
  document.querySelectorAll('.filters input:checked')
    .forEach(cb=>checked.add(cb.value));
  document.querySelectorAll('tr[data-source]').forEach(tr=>{{
    tr.classList.toggle('hidden',!checked.has(tr.dataset.source));
  }});
}}
</script>
</body></html>"""
