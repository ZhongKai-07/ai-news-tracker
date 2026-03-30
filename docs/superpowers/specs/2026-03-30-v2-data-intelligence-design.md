# AI News Trend Tracker V2 — 数据智能升级设计文档

**日期**：2026-03-30
**状态**：待实施
**目标用户**：个人开发者/技术爱好者（A）+ 团队内部工具（B），未来扩展至内容创作者（C）
**长期愿景**：热点趋势追踪 Agent

---

## 迭代概述

在 MVP 基础上进行三个模块的升级，核心目标：**提升数据质量 + 增加分析深度**。

| 模块 | 核心目标 | LLM 依赖 |
|------|----------|----------|
| 模块 1：数据清洗管道 | 消除 HTML 噪音、补全缺失数据、过滤低质量内容 | Tier 1（仅灰色地带） |
| 模块 2：语义关键词匹配 | 消除漏匹配和误匹配，提升核心链路准确率 | Tier 2 |
| 模块 3：深度分析 | 趋势解读、关联发现、异常预警 | Tier 1/2/3 |

---

## 数据流全景

```
RSS/Web 爬取
  → ① HTML净化（规则）
  → ② 数据补全（规则）
  → ③ 质量评分（规则 80% + Tier1 LLM 20%）
  → ④ 关键词匹配（规则强命中 + Tier2 LLM 语义精筛）
  → ⑤ 文章摘要（提取式，首段截取）
  → 入库

后置任务：
  → ⑥ 趋势快照更新（现有逻辑）
  → ⑦ 热点预警检查（规则触发 + Tier1 原因分析）
  → ⑧ 每日趋势解读（Tier2）
  → ⑨ 每周综合报告（Tier3）
  → ⑩ 关键词关联计算（纯统计，每周）
```

---

## 模块 1：数据清洗管道

在 crawler 抓取原始文章后、进入关键词匹配前，插入清洗管道。

### Step 1 — HTML 净化（规则层，零成本）

**输入**：爬取的原始 content

**处理**：
- 移除噪音标签：`<script>`, `<style>`, `<nav>`, `<footer>`, `<aside>`, `<iframe>`, `<form>`
- 移除广告类元素：class/id 包含 `ad`, `sponsor`, `promo`, `sidebar`, `comment` 的 `<div>`
- 提取正文：优先取 `<article>` 或 `<main>` 内的内容，回退到 `<body>`
- 输出纯文本，保留段落分隔

**输出**：`cleaned_content` 字段（Article 表新增）

### Step 2 — 数据补全（规则层，零成本）

| 字段 | 缺失时的回退策略 |
|------|------------------|
| `published_at` | RSS `updated` → RSS `published` → `fetched_at` |
| `title` | 如果为空或纯 URL → 取 content 前 80 字作为标题 |
| `content` | 为空时标记 `content_missing=True`，不阻塞流程 |

### Step 3 — 多信号质量评分（规则层，零成本）

给每篇文章计算 `quality_score`（0-100），根据分数分三档。

**信号 1 — 来源可信度（权重最大）**

DataSource 表新增 `trust_level` 字段：

| trust_level | 定义 | 示例 | 基础分 |
|-------------|------|------|--------|
| `high` | 知名技术博客/官方博客 | Anthropic Blog, OpenAI Blog, Google AI Blog | 80 |
| `medium` | 综合科技媒体/社区 | TechCrunch, Hacker News, ArsTechnica, InfoQ | 50 |
| `low` | 聚合站/未知来源 | 未归类的新 RSS 源 | 20 |

新添加的数据源默认 `trust_level=low`，用户可手动调整。

**信号 2 — 内容完整度**

| 条件 | 加/减分 |
|------|---------|
| content 长度 > 500 字 | +15 |
| content 长度 100-500 字 | +5 |
| content 长度 < 100 字或为空 | -20 |
| title 长度 10-100 字（正常范围） | +5 |
| title 过短（<10 字）或过长（>200 字） | -10 |

**信号 3 — URL/内容特征**

| 条件 | 加/减分 |
|------|---------|
| URL 含 `/ad/`, `/sponsor/`, `/redirect/`, `/campaign/` | -30 |
| title 含 "广告", "赞助", "sponsored", "AD" | -30 |
| 与已有文章标题相似度 > 90%（同一天内） | -25 |

**三档判定**：

| 档位 | 分数 | 处理 |
|------|------|------|
| 通过 | ≥ 60 | 直接进入关键词匹配 |
| 灰色地带 | 30-59 | 送 LLM 复核 |
| 过滤 | < 30 | 标记为 `filtered`，不参与匹配和趋势计算 |

### Step 4 — 灰色地带 LLM 批量复核（Tier 1，低成本）

仅处理 quality_score 30-59 的文章，预计占总量 10-20%。

- 每 20 篇打包一次，发送标题 + content 前 300 字 + 来源名称
- LLM 返回每篇的判定：`pass` 或 `reject`，附一句理由
- 通过的文章 `quality_score` 上调至 60，进入匹配流程
- 拒绝的标记为 `filtered`

**Prompt 结构**：
```
你是一个技术内容质量审核员。以下是一批文章，请判断每篇是否为有实质内容的技术文章。
排除：广告软文、纯转载无增量信息、过短无意义内容、非技术内容。
返回 JSON：[{"index": 1, "verdict": "pass/reject", "reason": "..."}]
```

---

## 模块 2：语义关键词匹配

替代现有纯子串匹配，采用规则快筛 + LLM 语义精筛的混合策略。

### 第一层：规则快筛（保留现有逻辑）

对每篇通过质量检查的文章，子串匹配所有关键词+别名：

| 结果 | 定义 | 处理 |
|------|------|------|
| 强命中 | 关键词在标题中完整匹配 | 直接确认，不需要 LLM |
| 弱命中 | 关键词仅在正文中匹配 | 保留，标记待 LLM 验证 |
| 未命中 | 没有子串匹配 | 送 LLM 做语义发现 |

### 第二层：LLM 语义精筛（Tier 2，批量调用）

将"弱命中"和"未命中"的文章打包，连同所有活跃关键词列表，一次调用 LLM：

```
以下是一批技术文章的标题和摘要，以及一组需要追踪的关键词。
请判断每篇文章与哪些关键词真正相关（语义层面，不要求字面出现）。

关键词列表：AI Agent, MCP, RAG, LLM, ...

文章列表：
1. 标题：xxx  摘要：xxx
2. 标题：xxx  摘要：xxx
...

返回 JSON：[{"index": 1, "matched_keywords": ["AI Agent"], "confidence": "high/medium", "reason": "..."}]
```

### 第三层：结果合并

| 来源 | 处理 |
|------|------|
| 规则强命中 | 直接入库，`match_method = "rule"` |
| LLM 确认（high confidence） | 入库，`match_method = "llm"` |
| LLM 确认（medium confidence） | 入库，`match_method = "llm_uncertain"` |
| LLM 未匹配 | 不创建 KeywordMention |

### 调用量预估

假设 200 篇文章通过质量清洗后剩余 140 篇：
- 强命中（标题匹配）：约 20%，28 篇，0 次 LLM
- 弱命中 + 未命中：约 112 篇，每 20 篇一批，约 6 次 LLM 调用

---

## 模块 3：深度分析

### 3.1 文章摘要生成（零 LLM 成本）

提取式摘要：取 `cleaned_content` 的前 1-2 个完整句子（不超过 100 字）。
技术文章的首段通常就是核心观点，效果够用。
存入 Article 表新增的 `summary` 字段。

### 3.2 趋势解读报告

**每日报告（Tier 2）**：每日爬取完成后自动生成。

输入给 LLM：
```
关键词 "AI Agent" 最近 7 天的数据：
- 提及次数变化：[3, 5, 4, 8, 12, 15, 20]
- 趋势方向：rising
- 相关文章标题（最近 5 篇）：
  1. "OpenAI launches new agent framework"
  2. "Google announces Agent2Agent protocol"
  ...
```

输出：
```json
{
  "summary": "AI Agent 本周热度显著上升，主要受 OpenAI 和 Google 相继发布 Agent 框架驱动",
  "key_drivers": ["OpenAI agent framework 发布", "Google A2A 协议发布"],
  "outlook": "预计短期内将持续升温"
}
```

**每周报告（Tier 3）**：每周生成一次，跨多天、多关键词综合分析。

### 3.3 关键词关联发现（纯统计，零 LLM 成本）

- 计算关键词共现矩阵（同一篇文章匹配到多个关键词的频率）
- 用余弦相似度或 Jaccard 系数量化关联强度
- 每周自动计算一次

### 3.4 热点异常预警

**规则触发（零 LLM 成本）**：
- 某关键词当日 mention_count ≥ 前 7 天均值的 3 倍 → 触发 `spike` 预警
- 某关键词连续 3 天上升且增速加快 → 触发 `sustained_rise` 预警

**原因分析（Tier 1）**：触发预警后，把相关文章标题打包送 LLM 生成一句话原因。

---

## LLM 服务架构

### 三级模型分层

| 级别 | 推荐模型 | 适用场景 | 特点 |
|------|----------|----------|------|
| Tier 1 | Qwen-Turbo / Kimi-Lite | 质量评分复核、预警原因分析 | 便宜、快，简单判断 |
| Tier 2 | Qwen-Plus / Kimi-2.5 标准版 | 关键词语义匹配、每日趋势解读 | 语义理解强，成本适中 |
| Tier 3 | Qwen-Max / Kimi-2.5 满血版 | 每周综合报告 | 深度推理，成本较高 |

### 统一调用层

后端新增 `llm_service.py`：
- 按 tier 路由到不同模型
- 支持批量调用（打包多篇文章）
- 内置重试和降级策略（Tier 2 失败降级到 Tier 1）
- 通过配置文件切换模型，不改业务代码

```python
llm_tier1_model = "qwen-turbo"
llm_tier2_model = "qwen-plus"
llm_tier3_model = "qwen-max"
```

### 成本预估

| 级别 | 调用频率 | 日成本估算 |
|------|----------|-----------|
| Tier 1 | ~10 次/天 | < ¥0.05 |
| Tier 2 | ~25 次/天 | < ¥0.5 |
| Tier 3 | 1 次/周 | < ¥0.1/天 |
| **合计** | | **< ¥1/天** |

---

## 数据库变更

### 现有表修改

**Article 表新增字段**：
- `cleaned_content: Text` — 清洗后的正文
- `quality_score: Integer` — 质量分数（0-100）
- `quality_tag: String` — `passed` / `filtered` / `pending_review`
- `summary: String` — 提取式摘要

**DataSource 表新增字段**：
- `trust_level: String` — `high` / `medium` / `low`，默认 `low`

**KeywordMention 表新增字段**：
- `match_method: String` — `rule` / `llm` / `llm_uncertain`
- `match_reason: String` — LLM 返回的匹配理由（可选）

### 新增表

**TrendReport 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `keyword_id` | FK → Keyword | 关联关键词 |
| `report_date` | Date | 报告日期 |
| `period` | String | `daily` / `weekly` |
| `summary` | Text | 趋势总结 |
| `key_drivers` | JSON | 驱动因素列表 |
| `outlook` | Text | 趋势展望 |
| `generated_at` | DateTime | 生成时间 |

**KeywordCorrelation 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `keyword_id_a` | FK → Keyword | 关键词 A |
| `keyword_id_b` | FK → Keyword | 关键词 B |
| `co_occurrence_count` | Integer | 共现次数 |
| `relationship` | Text | 关联说明 |
| `period_start` | Date | 统计周期起始 |
| `period_end` | Date | 统计周期结束 |

**Alert 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `keyword_id` | FK → Keyword | 关联关键词 |
| `alert_type` | String | `spike` / `sustained_rise` |
| `trigger_value` | Float | 触发时的数值 |
| `baseline_value` | Float | 基线数值 |
| `analysis` | Text | LLM 原因分析 |
| `created_at` | DateTime | 触发时间 |
| `is_read` | Boolean | 用户是否已读 |

---

## 新增后端服务

| 服务文件 | 职责 |
|----------|------|
| `llm_service.py` | 统一 LLM 调用层，Tier 1/2/3 路由，批量调用，重试/降级 |
| `content_cleaner.py` | HTML 净化 + 数据补全 |
| `quality_scorer.py` | 多信号规则评分 + LLM 灰色地带复核 |
| `semantic_matcher.py` | 规则快筛 + LLM 语义精筛（替代现有 keyword_matcher） |
| `trend_reporter.py` | 日报/周报生成 |
| `alert_service.py` | 预警规则检查 + 原因分析 |
| `correlation_service.py` | 共现矩阵计算 |

---

## 新增 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/trends/report` | GET | 查询趋势解读报告，参数：keyword_id, period(daily/weekly) |
| `/api/trends/correlations` | GET | 查询关键词关联，参数：keyword_id |
| `/api/alerts` | GET | 查询预警列表，参数：unread_only |
| `/api/alerts/{id}/read` | PUT | 标记预警已读 |
| `/api/sources/{id}/stats` | GET | 数据源质量统计（通过率等） |

---

## 前端展示

### Dashboard 页面

| 区域 | 内容 | 位置 |
|------|------|------|
| 预警通知栏 | 未读预警列表，红色高亮，点击展开原因分析 | 页面顶部 |
| 热点卡片增强 | 现有卡片下方增加 LLM 趋势摘要 | 现有卡片区域 |

### 趋势分析页

| 区域 | 内容 | 位置 |
|------|------|------|
| 趋势解读卡片 | 选中关键词后展示日报/周报 | 图表下方 |
| 关联关系展示 | 选中关键词时显示"相关话题"列表 | 右侧或图表下方 |

### 关键词管理页

| 区域 | 内容 | 位置 |
|------|------|------|
| 文章列表增强 | 展示文章摘要、质量标签、匹配方式 | 现有展开区域 |

### 数据源管理页

| 区域 | 内容 | 位置 |
|------|------|------|
| Trust Level 设置 | 表格新增"可信度"列，下拉切换 high/medium/low | 表格内 |
| 质量统计 | 每个源显示通过率 | 表格内 |

---

## 设计原则

1. **规则优先，LLM 兜底** — 能用计算解决的不用 LLM
2. **核心链路不省** — 关键词匹配准确率直接决定产品价值，用 Tier 2 模型保证效果
3. **批量调用** — 所有 LLM 调用都是批量（20-30 篇/次），不逐篇调用
4. **可降级** — Tier 2 失败可降级到 Tier 1，LLM 全挂可回退到纯规则匹配
5. **配置化** — 模型、阈值、评分权重均通过配置管理，不硬编码
