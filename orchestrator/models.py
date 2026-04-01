from dataclasses import dataclass, field


@dataclass
class NewsItem:
    """统一新闻条目，热榜和 RSS 共用"""
    id: str
    title: str
    url: str
    source: str
    source_type: str  # "hotlist" | "rss"
    rank: int = 0
    published_at: str = ""
    content: str = ""
    score: float = 0.0
    tags: list = field(default_factory=list)
    summary: str = ""
    pushed: bool = False


@dataclass
class ProcessResult:
    """单次处理结果"""
    total_fetched: int = 0
    total_matched: int = 0
    hotlist_count: int = 0
    rss_count: int = 0
    pushed_count: int = 0
    errors: list = field(default_factory=list)
