"""
InfoHub Orchestrator 主流程 v3 — 多租户 SaaS

改进：
- 所有模块接收 tenant_id
- 异步 PostgreSQL
- 用量计量
- 从数据库加载租户配置
"""

import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from config_loader import load_tenant_config
from hotlist import fetch_all_hotlists
from miniflux_client import MinifluxClient
from ai_processor import AIProcessor
from notifier import Notifier
from exporter import HTMLExporter, ObsidianExporter
from dedup import deduplicate
from db import Database
from metering import record_usage, check_quota

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("infohub")

TZ = timezone(timedelta(hours=8))


async def run(session: AsyncSession, tenant_id: UUID):
    config = await load_tenant_config(session, tenant_id)
    db = Database(session, tenant_id)
    run_id = await db.start_run()
    now = datetime.now(TZ)
    errors = []

    log.info(f"[{tenant_id}] 开始运行 #{run_id} - {now.strftime('%Y-%m-%d %H:%M')}")

    # ---- 0. Miniflux 客户端 + 自动注册源 ----
    mx = MinifluxClient(config["miniflux_url"], config["miniflux_api_key"])
    if config.get("sources"):
        mx.register_sources(config["sources"], config["rsshub_url"])

    # ---- 1. 抓取热榜 ----
    hotlist_items = fetch_all_hotlists(config.get("platforms"))
    log.info(f"[{tenant_id}] 热榜抓取完成: {len(hotlist_items)} 条")

    # ---- 2. 拉取 Miniflux RSS ----
    rss_items = mx.fetch_unread_entries(limit=200)
    log.info(f"[{tenant_id}] RSS 拉取完成: {len(rss_items)} 条")

    # ---- 3. 合并去重 ----
    all_items = deduplicate(hotlist_items + rss_items)
    new_items = await db.filter_new(all_items)
    log.info(f"[{tenant_id}] 去重后: {len(all_items)} 条, 新增: {len(new_items)} 条")

    if not new_items:
        log.info(f"[{tenant_id}] 无新增内容，跳过处理")
        _mark_miniflux_read(mx, rss_items)
        await db.finish_run(run_id,
                            hotlist_count=len(hotlist_items),
                            rss_count=len(rss_items),
                            dedup_count=len(all_items),
                            new_count=0, matched_count=0, pushed_count=0)
        return

    # ---- 4. AI 筛选（带配额检查）----
    ai = AIProcessor(config.get("ai", {}))
    matched = []
    if await check_quota(session, tenant_id, "ai_filter", requested=len(new_items)):
        matched = ai.filter_by_interest(new_items, config.get("interests", []))
        await record_usage(session, tenant_id, "ai_filter", count=len(new_items))
    else:
        log.warning(f"[{tenant_id}] AI 筛选配额已用完，跳过")
    log.info(f"[{tenant_id}] AI 筛选: {len(matched)}/{len(new_items)} 条匹配")

    # ---- 5. AI 翻译（英文标题翻中文）----
    if matched and config.get("ai", {}).get("api_key"):
        en_items = [it for it in matched
                    if it.source_type == "rss" and _is_english(it.title)]
        if en_items and await check_quota(session, tenant_id, "ai_translate", requested=len(en_items)):
            log.info(f"[{tenant_id}] 翻译 {len(en_items)} 条英文标题...")
            for it in en_items:
                translated = ai.translate(it.title)
                if translated != it.title:
                    it.title = f"{translated} | {it.title}"
            await record_usage(session, tenant_id, "ai_translate", count=len(en_items))
            log.info(f"[{tenant_id}] 翻译完成")

    # ---- 6. AI 摘要 ----
    summary = ""
    if matched and config.get("ai", {}).get("summary_enabled", True):
        if await check_quota(session, tenant_id, "ai_summary"):
            summary = ai.generate_summaries(matched)
            await record_usage(session, tenant_id, "ai_summary")
            log.info(f"[{tenant_id}] AI 摘要生成完成")

    # ---- 7. 存储 ----
    await db.save_items(all_items)
    await db.mark_matched(matched)

    # ---- 8. 输出 ----
    pushed_count = 0
    if matched:
        notifier = Notifier(config.get("notification", {}))
        success, fail = notifier.send(matched, now, summary=summary)
        if success > 0 and fail == 0:
            await db.mark_pushed([it.id for it in matched])
            pushed_count = len(matched)
            for channel in notifier.get_active_channels():
                await record_usage(session, tenant_id, f"push_{channel}")
            log.info(f"[{tenant_id}] 推送成功: {success} 个渠道")
        elif success > 0 and fail > 0:
            errors.append(f"推送部分失败: {success} 成功, {fail} 失败")
            log.warning(f"[{tenant_id}] 推送部分失败")
        elif fail > 0:
            errors.append(f"推送全部失败: {fail} 个渠道")
            log.error(f"[{tenant_id}] 推送全部失败")

        # HTML 报告
        html_exp = HTMLExporter(config["output_dir"], config.get("tenant_id", ""))
        html_exp.generate(matched, now, summary=summary)

        # Obsidian 导出
        vault_path = config.get("obsidian_vault_path")
        if vault_path:
            obs_exp = ObsidianExporter(vault_path)
            obs_exp.export(matched, now, summary=summary)

    # ---- 9. 标记 Miniflux 已读 ----
    _mark_miniflux_read(mx, rss_items)

    # ---- 10. 记录运行结果 ----
    await db.finish_run(run_id,
                        hotlist_count=len(hotlist_items),
                        rss_count=len(rss_items),
                        dedup_count=len(all_items),
                        new_count=len(new_items),
                        matched_count=len(matched),
                        pushed_count=pushed_count,
                        errors="; ".join(errors))

    log.info(f"[{tenant_id}] 运行完成 #{run_id} - "
             f"新增 {len(new_items)}, 匹配 {len(matched)}, "
             f"推送 {pushed_count}")


def _is_english(text: str) -> bool:
    """粗判是否英文（ASCII 字母占比 > 60%）"""
    if not text:
        return False
    ascii_count = sum(1 for c in text if c.isascii() and c.isalpha())
    return ascii_count / max(len(text), 1) > 0.6


def _mark_miniflux_read(mx, rss_items):
    """提取 Miniflux entry ID 并标记已读"""
    miniflux_ids = [
        getattr(item, '_miniflux_id', None) for item in rss_items
    ]
    miniflux_ids = [i for i in miniflux_ids if i is not None]
    if miniflux_ids:
        mx.mark_as_read(miniflux_ids)
