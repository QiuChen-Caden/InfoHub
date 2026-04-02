# InfoHub

一站式信息聚合与智能筛选平台。自动抓取多平台热榜 + RSS 订阅，经 AI 筛选、评分、摘要后，推送到 Telegram / 飞书 / 钉钉 / Slack / 邮件，并生成 HTML 报告和 Obsidian 笔记。

## 架构概览

```
┌─────────────┐    ┌──────────┐    ┌─────────────┐
│  11 大热榜   │    │  RSSHub  │    │ 外部 RSS 源  │
│  平台 API    │    │  (自建)   │    │             │
└──────┬──────┘    └────┬─────┘    └──────┬──────┘
       │                │                 │
       └────────┬───────┴─────────────────┘
                │
         ┌──────▼──────┐
         │  Miniflux   │  ← RSS 聚合层
         └──────┬──────┘
                │
       ┌────────▼────────┐
       │  Orchestrator   │  ← 核心编排层
       │  ┌────────────┐ │
       │  │ 跨源去重    │ │
       │  │ AI 兴趣筛选 │ │
       │  │ AI 翻译     │ │
       │  │ AI 摘要     │ │
       │  └────────────┘ │
       └───┬───┬───┬─────┘
           │   │   │
     ┌─────┘   │   └──────┐
     ▼         ▼          ▼
  推送通知   HTML报告   Obsidian
               │
        ┌──────▼──────┐
        │  FastAPI +   │  ← API 层
        │  React 前端  │
        └─────────────┘
```

## 功能特性

- **多源聚合** — 11 个中文热榜平台 + RSSHub 路由 + 外部 RSS，一次抓取全网热点
- **跨源去重** — URL 归一化 + 标题 bigram 相似度 + 来源优先级，消除重复信息
- **AI 智能筛选** — 基于自定义兴趣标签，AI 自动分类评分，只推送你关心的内容
- **AI 英文翻译** — 自动识别英文 RSS 标题并翻译为中文，中英对照阅读
- **AI 趋势摘要** — 对筛选结果进行趋势分析，提炼核心热点与弱信号
- **多渠道推送** — Telegram / 飞书 / 钉钉 / Slack / 邮件，按需配置
- **HTML 交互报告** — 带统计卡片、标签导航、来源筛选的暗色主题报告页
- **Obsidian 导出** — 自动生成带 frontmatter 的日报笔记，直接进入知识库
- **Web 管理面板** — React + Tailwind 构建的 Dashboard，查看运行状态、新闻列表、用量统计、配置管理
- **REST API** — FastAPI 提供数据查询接口，支持新闻筛选、运行记录、配置读写
- **定时调度** — 基于 croniter 的 Python 原生调度，默认每 30 分钟运行一次
- **AI 降级容错** — AI 服务不可用时自动降级为关键词匹配，保证基本可用
- **Docker 一键部署** — 全部服务容器化，`docker compose up` 即可运行

## 支持的热榜平台

| 平台 | ID |
|------|-----|
| 微博 | `weibo` |
| 知乎 | `zhihu` |
| 百度热搜 | `baidu` |
| 今日头条 | `toutiao` |
| 抖音 | `douyin` |
| B站热搜 | `bilibili-hot-search` |
| 贴吧 | `tieba` |
| 澎湃新闻 | `thepaper` |
| 凤凰网 | `ifeng` |
| 华尔街见闻 | `wallstreetcn-hot` |
| 财联社 | `cls-hot` |

## 快速开始

### 环境要求

- Docker 及 Docker Compose
- 不少于 2 GB 可用内存（推荐 4 GB）

### 1. 克隆项目

```bash
git clone https://github.com/QiuChen-Caden/InfoHub.git
cd InfoHub
```

### 2. 配置环境变量

复制并编辑 `.env` 文件：

```bash
cp .env.example .env
```

必填项：

```env
# 数据库
POSTGRES_PASSWORD=your_secure_password
INFOHUB_DB_PASSWORD=your_infohub_db_password

# Miniflux
MINIFLUX_ADMIN=admin
MINIFLUX_PASSWORD=your_password
MINIFLUX_API_KEY=your_miniflux_api_key

# AI（支持 DeepSeek / OpenAI / 任何 LiteLLM 兼容模型）
AI_API_KEY=your_api_key
AI_MODEL=deepseek/deepseek-chat
```

可选通知渠道（按需配置）：

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# 飞书
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx

# 钉钉
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx

# 邮件
EMAIL_FROM=you@example.com
EMAIL_PASSWORD=your_app_password
EMAIL_TO=recipient@example.com

# Obsidian 知识库路径
OBSIDIAN_VAULT_PATH=/path/to/your/vault
```

### 3. 启动服务

```bash
docker compose up -d
```

首次启动会自动：
- 初始化 PostgreSQL 数据库（创建 miniflux 和 infohub 两个库）
- 启动 RSSHub 实例（端口 3200）
- 配置 Miniflux 并创建管理员账户（端口 8880）
- 启动 API + 前端面板（端口 9090）
- 自动注册 `config/sources.yaml` 中的 RSS 订阅源
- 立即执行一次信息抓取

### 4. 获取 Miniflux API Key

启动后访问 `http://localhost:8880`，登录 Miniflux → 设置 → API 密钥 → 创建，将生成的 key 填入 `.env` 的 `MINIFLUX_API_KEY`，然后重启：

```bash
docker compose restart orchestrator api
```

### 5. 访问管理面板

浏览器打开 `http://localhost:9090`，可查看：
- **Dashboard** — 运行概览、最新统计
- **News** — 新闻列表，支持按来源、类型、分数、标签、时间筛选
- **Runs** — 历次 pipeline 运行记录
- **Usage** — AI 用量统计
- **Config** — 在线修改配置

## 配置说明

### 兴趣标签 — `config/interests.txt`

每行一个标签，AI 会将新闻归类到这些标签下：

```
AI与大模型
芯片半导体
智能汽车
中国科技公司
全球科技巨头
地缘政治
金融市场
开源项目
机器人具身智能
航天探索
```

### RSS 订阅源 — `config/sources.yaml`

支持 RSSHub 路由和外部 RSS 两种格式：

```yaml
rsshub_feeds:
  - route: /zhihu/hot
    name: 知乎热榜
    category: 中文热榜

  - route: /hackernews/best
    name: Hacker News Best
    category: 开发者

external_feeds:
  - url: https://hnrss.org/frontpage
    name: Hacker News
    category: 开发者
```

### 核心配置 — `config/config.yaml`

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `ai.model` | LLM 模型名称 | `deepseek/deepseek-chat` |
| `ai.min_score` | AI 筛选最低分数阈值 | `0.7` |
| `ai.batch_size` | 每批发送给 AI 的条目数 | `200` |
| `ai.max_tokens` | AI 单次最大 token 数 | `5000` |
| `ai.timeout` | AI 请求超时（秒） | `120` |
| `ai.summary_enabled` | 是否生成 AI 摘要 | `true` |
| `cron_schedule` | 定时调度表达式 | `*/30 * * * *` |
| `platforms` | 启用的热榜平台列表 | 全部 11 个 |

## 项目结构

```
InfoHub/
├── docker-compose.yml              # 服务编排（6 个容器）
├── Dockerfile.api                   # API + 前端多阶段构建
├── .env.example                     # 环境变量模板
├── init-db.sh                       # PostgreSQL 初始化脚本
├── config/
│   ├── config.yaml                  # 核心配置
│   ├── sources.yaml                 # RSS 订阅源配置
│   └── interests.txt                # 兴趣标签列表
├── orchestrator/
│   ├── Dockerfile                   # 编排层镜像
│   ├── entrypoint.sh                # 启动脚本（cron / api 双模式）
│   ├── requirements.txt             # Python 依赖
│   ├── main.py                      # 主流程（10 步 pipeline）
│   ├── cron_runner.py               # croniter 定时调度
│   ├── api.py                       # FastAPI REST API
│   ├── config_loader.py             # 配置加载 + 环境变量解析
│   ├── hotlist.py                   # 多平台热榜抓取
│   ├── miniflux_client.py           # Miniflux API 封装
│   ├── ai_processor.py              # AI 筛选 / 摘要 / 翻译
│   ├── dedup.py                     # 跨源去重引擎
│   ├── notifier.py                  # 多渠道通知推送
│   ├── exporter.py                  # HTML 报告 + Obsidian 导出
│   ├── db.py                        # PostgreSQL 数据存储
│   └── models.py                    # 数据模型
├── frontend/
│   ├── package.json                 # 前端依赖（Bun 管理）
│   ├── vite.config.ts               # Vite 构建配置
│   ├── tailwind.config.js           # Tailwind CSS 配置
│   └── src/
│       ├── main.tsx                 # React 入口
│       ├── App.tsx                  # 路由定义
│       ├── api.ts                   # API 请求封装
│       ├── types.ts                 # TypeScript 类型定义
│       ├── components/
│       │   ├── Layout.tsx           # 页面布局（侧边栏 + 顶栏）
│       │   ├── StatCard.tsx         # 统计卡片组件
│       │   └── NewsTable.tsx        # 新闻表格组件
│       └── pages/
│           ├── Dashboard.tsx        # 仪表盘
│           ├── News.tsx             # 新闻列表
│           ├── Runs.tsx             # 运行记录
│           ├── Usage.tsx            # 用量统计
│           └── Config.tsx           # 配置管理
└── output/
    └── html/                        # HTML 报告输出
        ├── latest/current.html      # 最新一期报告
        └── YYYY-MM-DD/              # 按日期归档
```

## 处理流程

每次调度运行执行以下 10 步 pipeline：

1. **初始化** — 加载配置，连接数据库，自动注册 RSS 源到 Miniflux
2. **抓取热榜** — 并发请求 11 个平台 API，带重试和退避
3. **拉取 RSS** — 通过 Miniflux API 获取未读条目
4. **合并去重** — URL 归一化 + 标题相似度去重，保留高优先级来源
5. **AI 筛选** — 按兴趣标签分类评分，过滤低相关度内容
6. **AI 翻译** — 英文 RSS 标题自动翻译为中文
7. **AI 摘要** — 生成趋势分析和核心热点提炼
8. **持久化** — 写入 PostgreSQL，记录评分和标签
9. **输出分发** — 推送通知 + 生成 HTML 报告 + 导出 Obsidian 笔记
10. **收尾** — 标记 Miniflux 已读，记录运行统计

## 技术栈

| 组件 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Tailwind CSS + Recharts |
| 前端构建 | Vite（Docker 内使用 [Bun](https://bun.sh) 安装依赖并构建） |
| API 层 | FastAPI + Uvicorn |
| RSS 聚合 | Miniflux + RSSHub |
| AI 引擎 | LiteLLM（兼容 DeepSeek / OpenAI / Claude 等） |
| 数据库 | PostgreSQL 16（Miniflux + InfoHub 业务数据） |
| 缓存 | Redis 7（RSSHub 缓存层） |
| 调度 | croniter（Python 原生调度） |
| Python 包管理 | [uv](https://github.com/astral-sh/uv)（Rust 实现，Docker 构建依赖安装） |
| 容器化 | Docker Compose |
| 语言 | Python 3.12 / TypeScript 5.6 |

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| API + 前端 | `9090` | Web 管理面板和 REST API |
| Miniflux | `8880` | RSS 聚合管理界面 |
| RSSHub | `3200` | RSS 路由服务 |

## 常见问题

**Q: 如何更换 AI 模型？**

修改 `.env` 中的 `AI_MODEL`，支持所有 [LiteLLM 兼容模型](https://docs.litellm.ai/docs/providers)，例如：
- `deepseek/deepseek-chat`
- `gpt-4o-mini`
- `claude-3-haiku-20240307`

**Q: 不配置 AI 能用吗？**

可以。不配置 `AI_API_KEY` 时，AI 筛选会降级为关键词匹配，翻译和摘要功能跳过，其余功能正常运行。

**Q: 如何添加新的热榜平台？**

编辑 `config/config.yaml` 中的 `platforms` 列表，可用平台 ID 见上方支持列表。

**Q: 如何只用 RSS 不用热榜？**

将 `config/config.yaml` 中的 `platforms` 设为空列表 `[]`。

**Q: Docker 构建很慢怎么办？**

项目已使用 [uv](https://github.com/astral-sh/uv)（Python）和 [Bun](https://bun.sh)（Node.js）替代 pip 和 npm，Docker 构建时依赖安装速度大幅提升。如果仍然很慢，检查网络连接或配置 Docker 镜像加速。

## License

MIT
