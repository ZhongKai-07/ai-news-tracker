# 概念/关键词趋势追踪系统 — 设计文档

## 概述

面向科技行业从业者的关键词趋势追踪系统，通过网络爬虫和RSS解析并行采集数据，生成带时间轴的热力图，展现概念热度趋势，支持多关键词不同颜色的热力度对比。

## 核心使用场景

- **日常监控（主）**：每天花几分钟查看关注的行业概念（如 Harness Engineering、Spec-driven Design）的热度变化
- **内容创作辅助（辅）**：发现热点话题，辅助选题

## 架构方案：渐进演进型

FastAPI + React + SQLite(本地)/PostgreSQL(部署) + asyncio并发爬取

- 本地开发零外部依赖，快速启动
- asyncio + aiohttp 并发爬取，无需Celery/Redis等中间件
- SQLAlchemy ORM 统一适配 SQLite 和 PostgreSQL，部署时平滑切换
- APScheduler 管理定时任务 + API支持手动触发

## 系统架构

```
┌─────────────────────────────────────────────────┐
│                  React 前端                      │
│  ┌──────────┐ ┌──────────────┐ ┌─────────────┐  │
│  │ 关键词管理 │ │ 热力图/趋势图 │ │ 内容创作面板 │  │
│  └──────────┘ └──────────────┘ └─────────────┘  │
└──────────────────┬──────────────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────────────┐
│               FastAPI 后端                       │
│  ┌──────────┐ ┌──────────┐ ┌─────────────────┐  │
│  │ API路由层 │ │ 调度服务  │ │ 热度计算引擎    │  │
│  └──────────┘ └────┬─────┘ └─────────────────┘  │
│                    │                             │
│  ┌─────────────────▼──────────────────────────┐  │
│  │           数据采集层 (asyncio)              │  │
│  │  ┌────────────┐  ┌─────────────────────┐   │  │
│  │  │ RSS 解析器  │  │ 网页爬虫 (aiohttp)  │   │  │
│  │  └────────────┘  └─────────────────────┘   │  │
│  └────────────────────────────────────────────┘  │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│     SQLite (本地) / PostgreSQL (部署)            │
│  ┌────────┐ ┌────────┐ ┌───────┐ ┌───────────┐  │
│  │ 数据源  │ │ 文章   │ │ 关键词 │ │ 热度快照  │  │
│  └────────┘ └────────┘ └───────┘ └───────────┘  │
└─────────────────────────────────────────────────┘
```

## 数据源

### 预置数据源

| 类型 | 数据源 | 采集方式 |
|------|--------|----------|
| 技术媒体 | Hacker News, TechCrunch, InfoQ, 36Kr | RSS + 爬虫 |
| 社交/社区 | Reddit(r/programming等), V2EX, 知乎热榜 | API + 爬虫 |
| 大厂博客 | OpenAI Blog, Google AI Blog, Anthropic Blog, Meta AI, 美团技术, 阿里技术, 字节技术 | RSS + 爬虫 |

### 数据源配置模型

```
DataSource:
  - name: 名称
  - type: rss | web_scraper | api
  - url: 源地址
  - parser_config: 解析规则(CSS选择器/XPath)
  - auth_config: 认证配置(JSON，如OAuth client_id/secret，存环境变量引用)
  - schedule: 抓取频率(cron表达式)
  - weight: 权重(影响热度计算)
  - enabled: 启用/禁用
  - status: normal | error | disabled
  - last_fetched_at: 上次抓取时间
  - last_error: 最近一次错误信息
  - consecutive_failures: 连续失败次数
  - proxy_url: 代理地址(可选)
  - custom_headers: 自定义HTTP请求头(JSON，可选)
```

- 需要认证的数据源（如Reddit OAuth2）通过 `auth_config` 配置，敏感凭证以环境变量名引用（如 `$REDDIT_CLIENT_ID`），不直接存储明文
- **反爬指数退避**：当 `consecutive_failures` 达到阈值（如3次），自动将该源的抓取间隔翻倍（指数退避），避免被源站永久封禁。恢复正常后自动还原频率
- 支持为每个数据源配置 `proxy_url` 和 `custom_headers`，应对不同源站的反爬策略

- RSS源优先，解析稳定成本低
- 爬虫作为补充，每个源单独配置解析规则
- 用户可自行添加新数据源

## 数据模型

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Keyword     │     │    Article        │     │  DataSource  │
├─────────────┤     ├──────────────────┤     ├─────────────┤
│ id           │     │ id                │     │ id               │
│ name         │     │ source_id (FK)    │────▶│ name             │
│ aliases (JSON)│    │ title             │     │ type             │
│ color        │     │ url (UNIQUE)      │     │ url              │
│ created_at   │     │ content           │     │ parser_config    │
│ is_active    │     │ published_at      │     │ auth_config      │
└──────┬──────┘     │ fetched_at        │     │ schedule         │
       │            └──────────────────┘     │ weight           │
       │                     │                │ enabled          │
       │                     │                │ status           │
       │                     │                │ last_fetched_at  │
       │                     │                │ last_error       │
       │                     │                │ consecutive_failures│
       │                     │                └──────────────────┘
       │     ┌───────────────┘
       ▼     ▼
┌──────────────────┐     ┌──────────────────┐
│ KeywordMention   │     │ TrendSnapshot    │
├──────────────────┤     ├──────────────────┤
│ id               │     │ id               │
│ keyword_id (FK)  │     │ keyword_id (FK)  │
│ article_id (FK)  │     │ date (日期粒度)   │
│ match_location   │     │ score            │
│ (title/content)  │     │ mention_count    │
│ context_snippet  │     └──────────────────┘
└──────────────────┘
```

- **Keyword.aliases**：JSON数组存储，支持多别名匹配，如 "Spec-driven Design" 也匹配 "规约驱动设计"、"specification-driven"
- **关键词匹配规则**：大小写不敏感的子串匹配，在文章抓取入库时执行匹配并写入 KeywordMention。匹配同时检查关键词名和所有别名
- **历史数据重算（Backfill）**：新增关键词或修改别名时，通过 `POST /api/keywords/{id}/rescan` 触发后台异步任务，对已入库的历史 Article 进行增量匹配，重新生成 KeywordMention 和 TrendSnapshot，确保新词也能看到历史趋势
- **KeywordMention**：记录命中位置（标题/正文）和上下文片段
- **TrendSnapshot**：每行 = 一个(keyword, date)组合，按天聚合（UTC时区）。前端按选定的时间窗口(7d/30d/90d)查询日期范围，直接渲染热力图。不存 period 字段，避免与按天粒度矛盾
- **时区规范**：后端所有时间戳和日期聚合统一使用 UTC。前端获取数据后根据浏览器本地时区进行偏移渲染，避免热力图在午夜发生数据漂移
- **Article.url**：设置 UNIQUE 约束，写入时使用 `INSERT OR IGNORE`(SQLite) / `ON CONFLICT DO NOTHING`(PostgreSQL) 防止并发去重问题

## 热力图与趋势对比

### 多关键词热力图对比

每个关键词分配不同色系，颜色深浅表示热度强度：

```
时间轴 →    3/1   3/7   3/14   3/21   3/28

AI Agent    ██▓▓  ████  █████  ████▓  █████   红色系
MCP         ░░▓▓  ▓▓██  █████  █████  █████   蓝色系
Spec-driven ░░░░  ░░▓▓  ▓▓▓▓  ▓▓██  ████▓   绿色系
```

### 两种可视化模式

1. **热力矩阵**：行=关键词，列=日期，颜色深浅=热度。适合同时对比多个关键词
2. **叠加趋势线**：多关键词不同颜色折线叠加，适合精确对比拐点

### 交互细节

- 自动分配色系（红、蓝、绿、紫、橙...），用户可自定义
- 悬停tooltip：日期、热度分、提及次数、来源分布
- 勾选/取消控制对比范围
- 时间窗口切换：7天 / 30天 / 90天

### 热度得分计算

- 基础分 = 时间段内关键词被提及的文章数
- 加权因素：数据源权重（如 Hacker News > 普通博客）、标题命中权重 2x > 正文命中权重 1x
- 归一化方式：对数归一化 `log(1 + score)`，适合处理高频词与低频词之间的巨大差异，使热力图颜色对比更直观

## 前端页面结构

### 1. Dashboard（首页）
- 顶部：已关注关键词的热度概览卡片，显示趋势箭头（↑↓→）
- 主区域：热力矩阵视图，所有关注关键词的近7天热度一览
- 右侧：最新抓取动态 — 最近匹配到的文章列表

### 2. 趋势分析页
- 关键词选择器（多选勾选）
- 时间范围切换：7天 / 30天 / 90天
- 双视图切换：热力矩阵 / 趋势折线
- 悬停tooltip显示详细数据

### 3. 关键词管理页
- 添加/编辑/删除关键词，配置别名和自定义颜色
- 关键词详情：命中文章列表、来源分布饼图

### 4. 数据源管理页
- 数据源列表（状态：正常/异常/禁用）
- 添加新数据源：URL、类型、解析规则
- 手动触发抓取、上次抓取时间、成功率统计

### 内容创作辅助（集成在Dashboard和趋势分析页）
- 「热门话题」标签：标记近期热度飙升的关键词
- 「趋势周报」按钮：一键生成周度趋势摘要文本

## API设计

```
关键词管理
  POST   /api/keywords            — 添加关键词（含别名、颜色）
  GET    /api/keywords            — 获取所有关键词
  PUT    /api/keywords/{id}       — 更新关键词
  DELETE /api/keywords/{id}       — 软删除关键词（设置 is_active=False，保留历史数据）
  POST   /api/keywords/{id}/rescan — 触发历史文章重新匹配（新增关键词或修改别名后使用）

趋势数据
  GET    /api/trends              — 查询热度数据
           ?keyword_ids=1,2,3&period=7d|30d|90d&start_date=&end_date=
  GET    /api/trends/heatmap      — 热力矩阵数据
  GET    /api/trends/hot          — 热度飙升关键词

文章/提及
  GET    /api/articles            — 文章列表（支持按关键词筛选）
  GET    /api/keywords/{id}/mentions — 某关键词的命中记录

数据源管理
  POST   /api/sources             — 添加数据源
  GET    /api/sources             — 数据源列表（含状态）
  PUT    /api/sources/{id}        — 更新数据源配置
  DELETE /api/sources/{id}        — 删除数据源

任务控制
  POST   /api/crawl/trigger       — 手动触发抓取（若已有抓取任务在运行则返回409）
  GET    /api/crawl/status        — 当前抓取状态（返回 idle | running，含进度信息）
  GET    /api/crawl/history       — 抓取历史记录

内容辅助
  GET    /api/summary/weekly      — 生成周度趋势摘要
           返回JSON：{keywords: [{name, trend, mention_count, top_articles}], period: "last_7_days"}
           纯数据聚合，不依赖LLM。汇总最近7个自然日内所有活跃关键词的趋势方向和Top文章
```

### 并发抓取互斥

- 后端维护一个 `crawl_lock`（asyncio.Lock），定时任务和手动触发共用
- 手动触发时若锁已被占用，返回 HTTP 409 并附上预计剩余时间
- 避免同一时刻两个抓取任务并行运行导致重复写入和源站限流

## 技术选型

| 层 | 技术 | 说明 |
|----|------|------|
| 后端框架 | FastAPI | 原生async支持，自动API文档 |
| 数据采集 | aiohttp + feedparser + BeautifulSoup | 异步爬虫 + RSS解析 + HTML解析 |
| 定时调度 | APScheduler | 轻量，支持cron表达式 |
| 数据库 | SQLite(本地) / PostgreSQL(部署) | SQLAlchemy ORM统一适配 |
| 前端框架 | React + TypeScript | 组件化开发 |
| 可视化 | ECharts | 热力图、折线图原生支持 |
| HTTP客户端 | Axios | 前端API调用 |
| 构建工具 | Vite | 快速开发体验 |

## 项目结构

```
ai-news/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI入口
│   │   ├── config.py              # 配置(DB切换等)
│   │   ├── models/                # SQLAlchemy模型
│   │   ├── routers/               # API路由
│   │   │   ├── keywords.py
│   │   │   ├── trends.py
│   │   │   ├── sources.py
│   │   │   └── crawl.py
│   │   ├── services/              # 业务逻辑
│   │   │   ├── crawler.py         # 爬虫调度
│   │   │   ├── rss_parser.py      # RSS解析
│   │   │   ├── web_scraper.py     # 网页爬虫
│   │   │   ├── keyword_matcher.py # 关键词匹配
│   │   │   └── trend_calculator.py # 热度计算
│   │   └── scheduler.py           # APScheduler配置
│   ├── requirements.txt
│   └── alembic/                   # 数据库迁移
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── TrendAnalysis.tsx
│   │   │   ├── KeywordManage.tsx
│   │   │   └── SourceManage.tsx
│   │   ├── components/
│   │   │   ├── HeatmapChart.tsx
│   │   │   ├── TrendLineChart.tsx
│   │   │   └── KeywordSelector.tsx
│   │   └── api/                   # API调用封装
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## 数据抓取策略

- **定时抓取**：APScheduler按各数据源配置的cron表达式定时执行
- **手动触发**：通过 POST /api/crawl/trigger 随时手动刷新
- **并发控制**：asyncio.Semaphore 限制单次抓取任务内同时爬取的源数量，避免被封IP。注：此 Semaphore 控制任务内并发；任务级别的互斥由 crawl_lock (asyncio.Lock) 保证，见"并发抓取互斥"章节
- **去重**：基于文章URL去重，避免重复入库
- **错误处理**：单个源失败不影响其他源，记录错误日志
