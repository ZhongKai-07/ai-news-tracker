# AI News Trend Tracker

AI 技术热点趋势追踪系统 — 自动爬取科技新闻，匹配关键词，可视化趋势热力图。

## 功能概览

- **RSS/网页爬取** — 定时抓取多个技术新闻源，支持 RSS 和网页抓取两种模式
- **关键词匹配** — 规则快筛 + LLM 语义精筛混合匹配，支持别名和多语言
- **趋势可视化** — ECharts 热力图 + 折线图，支持 7/30/90/120 天时间范围
- **数据清洗管道** — HTML 净化、数据补全、多信号质量评分、自动过滤低质量内容
- **LLM 智能分析** — 三级模型分层（Tier 1/2/3），质量复核、语义匹配、趋势解读（开发中）
- **数据源管理** — 可信度分级、爬取状态监控、失败指数退避

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11, FastAPI, SQLAlchemy 2.0 (async), SQLite (aiosqlite), APScheduler, Alembic |
| 前端 | React 18, TypeScript, Vite, ECharts, Axios |
| LLM | OpenAI-compatible API (Qwen/Kimi), 三级模型路由 |

## 快速开始

### 环境要求

- Python 3.11（不支持 3.14，pydantic-core 无预编译 wheel）
- Node.js 18+

### 后端

```bash
# 创建虚拟环境
cd backend
python3.11 -m venv ../.venv
source ../.venv/Scripts/activate   # Windows Git Bash
# source ../.venv/bin/activate     # macOS / Linux

# 安装依赖
pip install -r requirements.txt

# 运行服务
python -m uvicorn app.main:app --reload --port 8001

# 运行测试
python -m pytest tests/ -v
```

### 前端

```bash
cd frontend
npm install
npm run dev       # 开发服务器 :5173
npm run build     # 生产构建
```

### LLM 配置（可选）

在 `backend/.env` 中配置：

```env
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=sk-xxx
LLM_TIER1_MODEL=qwen-turbo
LLM_TIER2_MODEL=qwen-plus
LLM_TIER3_MODEL=qwen-max
```

不配置 LLM 时系统以纯规则模式运行，语义匹配和质量复核功能暂存待处理。

## 项目结构

```
ai-news-tracker/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口，lifespan 管理
│   │   ├── config.py            # pydantic-settings 配置
│   │   ├── database.py          # 异步 SQLAlchemy 引擎
│   │   ├── scheduler.py         # APScheduler（爬取 6h + LLM处理 10min）
│   │   ├── models/              # SQLAlchemy ORM 模型
│   │   │   ├── article.py       # 文章（含清洗内容、质量分数、摘要）
│   │   │   ├── data_source.py   # 数据源（含可信度等级）
│   │   │   ├── keyword.py       # 关键词（含别名）
│   │   │   ├── keyword_mention.py  # 关键词匹配记录（含匹配方式）
│   │   │   ├── trend_snapshot.py   # 趋势快照
│   │   │   ├── trend_report.py     # 趋势报告 (V2)
│   │   │   ├── keyword_correlation.py  # 关键词关联 (V2)
│   │   │   └── alert.py            # 热点预警 (V2)
│   │   ├── services/            # 业务逻辑
│   │   │   ├── crawler.py       # 爬虫服务（含数据清洗管道集成）
│   │   │   ├── content_cleaner.py  # HTML 净化 + 数据补全 + 摘要提取
│   │   │   ├── quality_scorer.py   # 多信号质量评分
│   │   │   ├── keyword_matcher.py  # 规则关键词匹配
│   │   │   ├── semantic_matcher.py # 规则 + LLM 混合语义匹配
│   │   │   ├── title_dedup.py      # Jaccard 标题去重
│   │   │   ├── llm_service.py      # LLM 统一调用层（路由+重试+熔断）
│   │   │   ├── llm_process_job.py  # LLM 定时处理 Job
│   │   │   ├── trend_calculator.py # 趋势计算
│   │   │   ├── rss_parser.py       # RSS 解析
│   │   │   └── web_scraper.py      # 网页抓取
│   │   └── routers/             # API 路由
│   │       ├── articles.py      # 文章列表 + 匹配详情
│   │       ├── keywords.py      # 关键词 CRUD + 重新扫描
│   │       ├── sources.py       # 数据源 CRUD
│   │       ├── trends.py        # 热力图/热点/趋势
│   │       ├── crawl.py         # 手动触发爬取
│   │       └── summary.py       # 周报摘要
│   ├── alembic/                 # 数据库迁移
│   └── tests/                   # 93 个测试
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.tsx    # 仪表盘（热点卡片 + 热力图）
│       │   ├── TrendAnalysis.tsx # 趋势分析（多关键词对比）
│       │   ├── KeywordManage.tsx # 关键词管理
│       │   └── SourceManage.tsx  # 数据源管理
│       ├── components/          # ECharts 图表组件
│       └── api/client.ts        # API 客户端
└── docs/                        # 设计文档 + 实施计划
```

## 数据流

```
RSS/Web 爬取
  → HTML 净化（规则）
  → 数据补全（规则）
  → 质量评分（规则）
  → 提取式摘要（规则）
  → 关键词规则快筛（标题强命中直接入库）
  → 入库

LLM 定时 Job（每 10 分钟，独立于爬取）
  → 标题相似度去重
  → 灰色地带文章质量复核（Tier 1）
  → 语义关键词匹配（Tier 2）
  → 更新趋势快照
```

## 开发状态

V2 Data Intelligence 升级进行中，分支 `v2-data-intelligence`：

| Chunk | 内容 | 状态 |
|-------|------|------|
| 1 | DB 模型扩展、Config、LLM Service、Alembic | 已完成 |
| 2 | 数据清洗管道 | 已完成 |
| 3 | 语义匹配 + LLM 定时 Job | 已完成 |
| 4 | 深度分析（预警、趋势报告、关联） | 待开始 |
| 5 | API 端点 + 前端页面 | 待开始 |
| 6 | 集成测试 + 端到端验证 | 待开始 |

## License

MIT
