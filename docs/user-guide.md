# AI News Trend Tracker - 用户使用手册

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- pip / npm

### 启动系统

**1. 启动后端**

```bash
cd backend
source ../.venv/Scripts/activate   # Windows Git Bash
# source ../.venv/bin/activate     # macOS / Linux
python -m uvicorn app.main:app --reload --port 8001
```

启动后访问 http://localhost:8001/docs 可查看 API 文档（Swagger UI）。

**2. 启动前端**

```bash
cd frontend
npm run dev
```

启动后访问 http://localhost:5173 进入系统界面。

---

## 功能说明

### 1. Dashboard（首页）

首页提供全局概览：

- **关键词卡片**：每个关注的关键词显示一张卡片，带颜色标识和趋势方向（^ 上升 / v 下降 / - 稳定）
- **Hot Topics**：近 7 天热度飙升的关键词高亮显示
- **7 天热力图**：所有关注关键词的近 7 天热度矩阵，颜色越深表示热度越高

### 2. Trends（趋势分析）

深度对比分析页面：

- **关键词选择器**：勾选/取消勾选要对比的关键词
- **时间范围切换**：点击 `7d` / `30d` / `90d` 按钮切换时间窗口
- **双视图模式**：
  - **Heatmap**：热力矩阵视图，行=关键词，列=日期，颜色深浅=热度
  - **Trend Lines**：折线图视图，多关键词不同颜色叠加，适合精确对比拐点
- **悬停查看详情**：鼠标悬停在数据点上可查看具体日期、热度分数、提及次数

### 3. Keywords（关键词管理）

管理你关注的行业概念：

**添加关键词**
1. 在顶部输入框填写关键词名称（如 `AI Agent`）
2. 填写别名，用逗号分隔（如 `AI助手, intelligent agent`）— 系统会同时匹配名称和所有别名
3. 选择颜色（用于图表中区分不同关键词）
4. 点击 `Add`

**编辑关键词**
- 点击关键词行的 `Edit` 按钮，修改后点击 `Update`

**重新扫描（Rescan）**
- 添加新关键词或修改别名后，点击 `Rescan` 可对已入库的历史文章重新匹配
- 这样新关键词也能看到历史趋势数据

**删除关键词**
- 点击 `Delete` 执行软删除（数据保留，仅从列表隐藏）

### 4. Sources（数据源管理）

配置你的信息采集源：

**添加数据源**
1. 填写名称（如 `Hacker News`）
2. 选择类型：
   - **RSS**：RSS 订阅源（推荐，最稳定）
   - **Web Scraper**：网页爬虫（需配置解析规则）
   - **API**：API 接口
3. 填写 URL（如 `https://hnrss.org/newest`）
4. 设置权重（影响热度计算，默认 1.0，重要来源可设为 2.0）
5. 点击 `Add Source`

**手动触发抓取**
- 点击右上角 `Trigger Crawl` 按钮立即执行一次全量抓取
- 抓取进行中按钮会显示 `Crawling...` 状态
- 抓取完成后数据源列表会自动刷新

**数据源状态说明**
- **normal**（绿色）：正常运行
- **error**（红色）：连续失败 3 次以上，系统自动降低抓取频率（指数退避）
- **Failures** 列：显示连续失败次数

**删除数据源**
- 点击 `Delete` 永久删除该数据源

---

## 推荐数据源

以下是一些常用的 RSS 源，可直接添加：

| 名称 | URL | 建议权重 |
|------|-----|---------|
| Hacker News | `https://hnrss.org/newest` | 2.0 |
| TechCrunch | `https://techcrunch.com/feed/` | 1.5 |
| The Verge | `https://www.theverge.com/rss/index.xml` | 1.0 |
| Ars Technica | `https://feeds.arstechnica.com/arstechnica/index` | 1.0 |
| InfoQ | `https://feed.infoq.com/` | 1.5 |
| OpenAI Blog | `https://openai.com/blog/rss.xml` | 2.0 |
| Google AI Blog | `https://blog.google/technology/ai/rss/` | 2.0 |
| Anthropic Blog | `https://www.anthropic.com/rss.xml` | 2.0 |

---

## 自动抓取

系统内置定时任务，每 **6 小时** 自动执行一次全量抓取。无需手动干预，后端运行期间会持续更新数据。

你也可以随时点击 `Trigger Crawl` 手动刷新。如果定时任务正在运行，手动触发会返回提示"Crawl already running"。

---

## 热度计算规则

系统按以下规则计算每日热度得分：

1. **基础权重**：标题命中 = 2 分，正文命中 = 1 分
2. **数据源权重**：乘以该数据源的权重值（如 Hacker News 权重 2.0，则标题命中 = 4 分）
3. **对数归一化**：最终得分 = `log(1 + 原始分)`，使高频词和低频词能在同一坐标系下直观对比

---

## API 接口

后端提供完整的 REST API，访问 http://localhost:8001/docs 查看交互式文档。

主要接口：

| 接口 | 说明 |
|------|------|
| `GET /api/keywords` | 获取所有活跃关键词 |
| `POST /api/keywords` | 添加关键词 |
| `POST /api/keywords/{id}/rescan` | 重新扫描历史文章 |
| `GET /api/sources` | 获取数据源列表 |
| `POST /api/sources` | 添加数据源 |
| `GET /api/trends/heatmap?period=7d` | 获取热力图数据 |
| `GET /api/trends/hot` | 获取热度飙升关键词 |
| `POST /api/crawl/trigger` | 手动触发抓取 |
| `GET /api/crawl/status` | 查询抓取状态 |
| `GET /api/articles?keyword_id=1` | 按关键词筛选文章 |
| `GET /api/summary/weekly` | 获取周度趋势摘要 |

---

## 常见问题

**Q: 添加关键词后热力图没有数据？**
A: 需要先添加数据源并执行一次抓取（点击 Trigger Crawl）。如果关键词是后加的，点击 Rescan 重新匹配历史文章。

**Q: 数据源状态显示 error？**
A: 连续抓取失败 3 次以上。可能原因：URL 错误、源站不可用、网络问题。系统会自动指数退避，恢复后自动回到正常状态。

**Q: 能同时对比多少个关键词？**
A: 没有硬性限制。建议同时对比不超过 10 个，以保证图表可读性。

**Q: 别名匹配的规则是什么？**
A: 大小写不敏感的子串匹配。例如关键词 "MCP" 会匹配包含 "mcp"、"MCP"、"Mcp" 的标题和正文。

**Q: 如何修改自动抓取的频率？**
A: 修改 `backend/app/scheduler.py` 中的 `hours=6` 参数，重启后端生效。
