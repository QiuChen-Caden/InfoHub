"""AI 筛选、摘要、翻译 - 基于 LiteLLM"""

import json
import time
import logging
from typing import List

from json_repair import repair_json
from litellm import completion

from models import NewsItem

log = logging.getLogger("infohub.ai")


class AIProcessor:
    def __init__(self, config: dict):
        self.model = config.get("model", "deepseek/deepseek-chat")
        self.api_key = config.get("api_key", "")
        self.api_base = config.get("api_base") or None
        self.timeout = config.get("timeout", 120)
        self.max_tokens = config.get("max_tokens", 5000)
        self.batch_size = config.get("batch_size", 200)
        self.batch_interval = config.get("batch_interval", 2)
        self.min_score = config.get("min_score", 0.7)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """统一 LLM 调用"""
        resp = completion(
            model=self.model,
            api_key=self.api_key,
            api_base=self.api_base,
            timeout=self.timeout,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content

    def filter_by_interest(self, items: List[NewsItem],
                           interests: List[str]) -> List[NewsItem]:
        """AI 兴趣筛选，返回匹配条目"""
        if not self.api_key:
            log.warning("未配置 AI API Key，跳过 AI 筛选，返回全部")
            return items

        tags_str = "\n".join(f"- {t}" for t in interests)
        tags_list_str = "、".join(interests)
        matched = []

        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            titles = "\n".join(
                f"{j+1}. [{it.source}] {it.title}"
                for j, it in enumerate(batch)
            )

            system = (
                f"你是新闻分类专家。将新闻归类到以下兴趣标签中并评分。\n\n"
                f"【可用标签（只能从中选择）】\n{tags_str}\n\n"
                f"【规则】\n"
                f"1. tag 字段必须是以上标签之一，禁止使用其他值\n"
                f"2. 如果新闻不属于任何标签，不要返回该条\n"
                f"3. score 范围 0-1，只返回 score >= {self.min_score} 的\n"
                f"4. 返回纯 JSON 数组，每条: {{\"index\": 序号, \"score\": 分数, \"tag\": \"{tags_list_str}其中之一\"}}\n"
                f"5. 不要输出任何解释，只输出 JSON"
            )

            try:
                raw = self._call_llm(system, titles)
                results = json.loads(repair_json(raw))
                for r in results:
                    idx = r.get("index", 0) - 1
                    if 0 <= idx < len(batch):
                        batch[idx].score = r.get("score", 0)
                        tag = r.get("tag", "")
                        # 强制校验 tag 必须在兴趣列表中
                        if tag not in interests:
                            tag = _best_match_tag(tag, interests)
                        batch[idx].tags = [tag]
                        if batch[idx].score >= self.min_score:
                            matched.append(batch[idx])
            except Exception as e:
                log.error(f"AI 筛选批次失败: {e}, 降级为关键词匹配")
                fallback = _keyword_fallback(batch, interests)
                matched.extend(fallback)
                log.info(f"关键词 fallback: {len(fallback)}/{len(batch)} 条")

            if i + self.batch_size < len(items):
                time.sleep(self.batch_interval)

        return matched

    def generate_summaries(self, items: List[NewsItem]):
        """为匹配条目生成 AI 摘要"""
        if not self.api_key:
            return

        titles = "\n".join(
            f"- [{it.source}] {it.title} (标签: {','.join(it.tags)})"
            for it in items[:150]
        )

        system = (
            "你是趋势分析专家。对以下新闻进行分析：\n"
            "1. 核心热点与趋势（3-5 条）\n"
            "2. 值得关注的弱信号\n"
            "3. 简要研判\n\n"
            "用中文回答，简洁有力。"
        )

        try:
            summary = self._call_llm(system, titles)
            if items:
                items[0].summary = summary
        except Exception as e:
            log.error(f"AI 摘要失败: {e}")

    def translate(self, text: str, target_lang: str = "中文") -> str:
        """AI 翻译 — 仅翻译标题，不解释"""
        if not self.api_key:
            return text
        try:
            result = self._call_llm(
                f"你是翻译器。将以下标题翻译为{target_lang}。"
                f"只输出翻译结果，不要解释、不要加引号、不要多余内容。"
                f"翻译结果必须在30字以内。",
                text,
            )
            # 校验：翻译结果不应比原文长3倍，否则说明模型在胡说
            result = result.strip().strip('"').strip("'")
            if len(result) > len(text) * 3 or "\n" in result:
                return text
            return result
        except Exception:
            return text


def _keyword_fallback(items: List[NewsItem],
                      interests: List[str]) -> List[NewsItem]:
    """AI 失败时的关键词降级筛选"""
    matched = []
    for item in items:
        for tag in interests:
            if tag in item.title:
                item.tags = [tag]
                item.score = 0.5  # 低置信度标记
                matched.append(item)
                break
    return matched


def _best_match_tag(tag: str, interests: List[str]) -> str:
    """将非法 tag 映射到最接近的兴趣标签"""
    if not tag or not interests:
        return interests[0] if interests else "其他"
    for t in interests:
        if t in tag or tag in t:
            return t
    best, best_score = interests[0], 0
    for t in interests:
        overlap = len(set(tag) & set(t))
        if overlap > best_score:
            best, best_score = t, overlap
    return best
