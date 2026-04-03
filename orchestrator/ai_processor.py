"""AI 筛选、摘要、翻译 - 基于 LiteLLM"""

import json
import time
import logging
from typing import List

from json_repair import repair_json
from litellm import completion
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from models import NewsItem

log = logging.getLogger("infohub.ai")

# LLM 调用可重试的异常类型
_RETRYABLE = (ConnectionError, TimeoutError, OSError)


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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(_RETRYABLE),
        reraise=True,
        before_sleep=lambda retry_state: log.warning(f"LLM 重试 #{retry_state.attempt_number}, 等待 {retry_state.next_action.sleep:.0f}s"),
    )
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """统一 LLM 调用，带重试"""
        t0 = time.time()
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
        elapsed = time.time() - t0
        log.info(f"LLM 调用 {self.model} 耗时 {elapsed:.1f}s")
        return resp.choices[0].message.content

    def filter_by_interest(self, items: List[NewsItem],
                           interests: List[str]) -> List[NewsItem]:
        """AI 兴趣筛选，返回匹配条目"""
        if not self.api_key:
            log.warning("未配置 AI API Key，跳过 AI 筛选，返回全部")
            return items

        log.info(f"AI 筛选开始: {len(items)} 条, {len(interests)} 个标签, 分 {(len(items) + self.batch_size - 1) // self.batch_size} 批")

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

    def generate_summaries(self, items: List[NewsItem]) -> str:
        """为匹配条目生成 AI 摘要，返回摘要文本"""
        if not self.api_key:
            return ""

        titles = "\n".join(
            f"- [{it.source}] {it.title} (标签: {','.join(it.tags)})"
            for it in items[:150]
        )
        if len(items) > 150:
            log.warning(f"AI 摘要截断: 共 {len(items)} 条，仅取前 150 条")

        system = (
            "你是趋势分析专家。对以下新闻进行分析：\n"
            "1. 核心热点与趋势（3-5 条）\n"
            "2. 值得关注的弱信号\n"
            "3. 简要研判\n\n"
            "用中文回答，简洁有力。"
        )

        try:
            t0 = time.time()
            result = self._call_llm(system, titles)
            elapsed = time.time() - t0
            log.info(f"AI 摘要生成耗时 {elapsed:.1f}s, {len(items)} 条输入")
            return result
        except Exception as e:
            log.error(f"AI 摘要失败: {e}")
            return ""

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
            result = result.strip().strip('"').strip("'")
            if len(result) > len(text) * 3 or "\n" in result:
                return text
            return result
        except Exception as e:
            log.debug(f"单条翻译失败: {e}")
            return text

    def translate_batch(self, titles: list[str], target_lang: str = "中文") -> list[str]:
        """批量翻译标题，一次 LLM 调用翻译多条"""
        if not self.api_key or not titles:
            return titles

        log.info(f"批量翻译: {len(titles)} 条, 分 {(len(titles) + 19) // 20} 批")

        results = list(titles)  # 默认保持原文
        for i in range(0, len(titles), 20):
            batch = titles[i:i + 20]
            numbered = "\n".join(f"{j+1}. {t}" for j, t in enumerate(batch))
            try:
                raw = self._call_llm(
                    f"你是翻译器。将以下编号标题逐条翻译为{target_lang}。\n"
                    f"【规则】\n"
                    f"1. 每行输出格式: 编号. 翻译结果\n"
                    f"2. 只输出翻译，不解释\n"
                    f"3. 每条翻译不超过30字\n"
                    f"4. 保持编号顺序一致",
                    numbered,
                )
                for line in raw.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    # 解析 "1. 翻译结果"
                    dot_pos = line.find(".")
                    if dot_pos > 0 and dot_pos <= 3:
                        try:
                            idx = int(line[:dot_pos]) - 1
                            translated = line[dot_pos+1:].strip().strip('"').strip("'")
                            if 0 <= idx < len(batch) and translated and len(translated) <= len(batch[idx]) * 3:
                                results[i + idx] = translated
                        except ValueError:
                            continue
            except Exception as e:
                log.warning(f"批量翻译失败: {e}, 跳过该批次")

        translated_count = sum(1 for orig, res in zip(titles, results) if orig != res)
        log.info(f"批量翻译完成: {translated_count}/{len(titles)} 条实际翻译")
        return results


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
