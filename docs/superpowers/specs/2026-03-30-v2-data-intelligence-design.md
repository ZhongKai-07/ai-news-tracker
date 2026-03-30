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
| 与已有文章标题相似度 > 90%（同一天内，阶段二后台计算） | -25 |

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

提取式摘要，基于 `cleaned_content`：
- 跳过短行（< 20 字，通常是署名、日期、图片说明）
- 句子切分：中文按 `。！？` 分割；英文用保守正则 `(?<=[.!?])\s+(?=[A-Z])` 分割（避免 `e.g.`, `U.S.` 等缩写误切）
- 取第一个符合长度的完整句子（20-200 字）
- 如果找不到合适句子，取前 100 字并截断到最后一个标点
- 存入 Article 表新增的 `summary` 字段
- **质量预期**：够用级别，不追求完美。极少数清洗后仍混乱的文章，摘要可能不理想，可接受

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
- `needs_llm_matching: Boolean` — 是否需要 LLM 语义匹配（阶段二处理标记），默认 False

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

## 爬取管道集成方案

### 修改后的爬取流程

当前 `_process_article` 在 `crawler.py` 中逐篇处理（创建文章 → 关键词匹配 → 趋势快照更新），全部在单个 per-source session 内完成。新管道需要分两阶段：

**阶段一：同步处理（在现有 `_crawl_source` 内）**

```
对每篇文章：
  1. URL 去重检查（现有逻辑）
  2. HTML 净化（规则，毫秒级）
  3. 数据补全（规则，毫秒级）
  4. 多信号质量评分（规则，毫秒级）
  5. 提取式摘要生成（规则，毫秒级）
  6. 创建 Article 记录，写入 cleaned_content, quality_score, summary
  7. quality_score ≥ 60 → 规则快筛关键词匹配
     - 标题强命中 → 直接创建 KeywordMention (match_method="rule") + 更新 TrendSnapshot
     - 弱命中/未命中 → 标记 article 为 needs_llm_matching=True
  8. quality_score 30-59 → 标记 quality_tag="pending_review"
  9. quality_score < 30 → 标记 quality_tag="filtered"，跳过匹配
```

阶段一全是规则操作，不增加任何延迟。保留现有的 per-source session 架构。

**阶段二：独立定时 Job（与爬取完全解耦）**

阶段二不再绑定在单次爬取的生命周期内，而是作为 APScheduler 的独立 Job 运行（建议间隔 10-15 分钟），从数据库中消费待处理的文章。这样彻底解耦爬取管道和 LLM 处理管道：爬取不等 LLM，LLM 不依赖爬取是否完成。

```
llm_process_job()（APScheduler 独立 Job，每 10-15 分钟运行一次）:
  1. 查询所有 quality_tag="pending_review" 的文章
     → 批量打包（每 20 篇）→ Tier 1 LLM 质量复核
     → 通过的更新为 quality_tag="passed"，标记 needs_llm_matching=True
     → 拒绝的更新为 quality_tag="filtered"

  2. 查询所有 needs_llm_matching=True 的文章
     → 批量打包（每 20 篇）+ 活跃关键词列表 → Tier 2 LLM 语义匹配
     → 创建 KeywordMention (match_method="llm"/"llm_uncertain")
     → 在同一事务内顺序更新对应 TrendSnapshot（见并发安全说明）
     → 更新 needs_llm_matching=False

  3. 运行热点预警检查（规则触发 + Tier 1 原因分析）
  4. 生成每日趋势解读（Tier 2，仅在当天首次有新匹配数据时生成）
```

阶段二使用自己的 DB session，通过 `needs_llm_matching` 和 `quality_tag` 标记从数据库消费待处理文章。如果某次运行时无积压文章，Job 直接跳过。

**TrendSnapshot 并发安全**：SQLite 是单写者模型，同一时刻只有一个事务能写入。阶段二的 TrendSnapshot 更新在同一事务内顺序执行（逐条处理同一关键词+日期的 snapshot），不存在并发写入 Lost Update 的风险。阶段一（爬取中的规则强命中）和阶段二（LLM 匹配结果）的写入在时间上天然错开（阶段二在爬取之后运行），不会冲突。

**关键词数量优化**：当活跃关键词 > 30 个时，LLM prompt 中仅发送尚未被规则强命中的关键词（即排除已在阶段一匹配到的），减少 prompt 长度。

---

## 数据迁移策略

使用 Alembic 进行数据库迁移。

### 现有数据处理

| 表 | 新字段 | 现有数据处理 |
|----|--------|-------------|
| Article | `cleaned_content` | 设为 NULL，后续可运行一次性脚本回填 |
| Article | `quality_score` | 设为 NULL（表示未评分） |
| Article | `quality_tag` | 默认 `passed`（现有文章视为已通过） |
| Article | `summary` | 设为 NULL，后续可批量生成 |
| Article | `needs_llm_matching` | 默认 False（现有匹配结果保留） |
| DataSource | `trust_level` | 默认 `medium`（现有源视为中等可信） |
| KeywordMention | `match_method` | 默认 `rule`（现有匹配均为规则匹配） |
| KeywordMention | `match_reason` | 设为 NULL |

### 向后兼容

- 语义匹配在 `cleaned_content` 为 NULL 时回退使用 `content`
- 质量评分在 `quality_score` 为 NULL 时跳过过滤
- 前端在 `summary` 为 NULL 时不显示摘要区域

---

## 标题相似度去重

用于质量评分信号 3 中的重复检测。**在阶段二定时 Job 中后台执行，不在阶段一实时流程中运行**（当前已有 URL 唯一约束做绝对去重，标题相似度是补充性清洗）。

**算法**：基于 token 的 Jaccard 相似度
- 将标题分词（中文用字符级 bigram，英文用空格分词后小写化）
- Jaccard = |A ∩ B| / |A ∪ B|
- 阈值 > 0.9 判定为重复

**执行方式**：
- 在 `llm_process_job` 的步骤 1 之前运行，作为阶段二的预处理
- 仅对当天新入库且 `quality_tag != "filtered"` 的文章做两两比较
- 重复文章中保留来源 `trust_level` 最高的，其余标记为 `quality_tag="filtered"`
- 先用标题长度差异快速预过滤（长度差 > 50% 的直接跳过），减少实际比较次数

---

## LLM 失败处理

### 重试与降级策略

| 场景 | 处理 |
|------|------|
| 单次调用超时 | 超时阈值 30 秒，最多重试 2 次（间隔 2s, 5s） |
| 重试仍失败 | Tier 2 降级到 Tier 1 重试 1 次 |
| 降级仍失败 | 该批次文章标记保留（`needs_llm_matching=True`），等下次 Job 运行时重试 |
| LLM 全面不可用 | 系统回退到纯规则模式：仅规则强命中入库，灰色地带文章暂存 |
| LLM 恢复后 | 下次 `llm_process_job` 运行时自动拾取所有积压的 `needs_llm_matching=True` 和 `pending_review` 文章 |

### 断路器

- 连续 5 次 LLM 调用失败 → 开启断路器，后续调用直接跳过（不浪费时间等超时）
- 每 10 分钟尝试一次探针调用，成功则关闭断路器
- 断路器状态记录在内存中（随服务重启重置）

---

## 数据库约束补充

### 新增唯一约束

- **TrendReport**：`UniqueConstraint(keyword_id, report_date, period)` — 防止重复生成报告
- **KeywordCorrelation**：`UniqueConstraint(keyword_id_a, keyword_id_b, period_start, period_end)` — 防止重复计算
  - 约定 `keyword_id_a < keyword_id_b`，保证方向一致性

### Alert 表补充字段

- `analysis_status: String` — `pending` / `completed` / `failed`，跟踪 LLM 分析生成状态
  - 规则触发时创建 Alert，`analysis_status=pending`
  - LLM 生成成功后更新为 `completed`
  - LLM 失败后标记为 `failed`，前端显示"分析生成中"或"分析失败"

### quality_score 约束

- 计算完成后 clamp 到 [0, 100]：`quality_score = max(0, min(100, raw_score))`

### 新增索引

| 表 | 索引 | 用途 |
|----|------|------|
| Article | `idx_article_quality_tag` on (quality_tag) | 快速查询 pending_review 文章 |
| Article | `idx_article_needs_llm` on (needs_llm_matching) | 快速查询待 LLM 匹配文章 |
| Alert | `idx_alert_unread` on (is_read, created_at) | 查询未读预警 |
| TrendReport | `idx_report_keyword_date` on (keyword_id, report_date) | 查询特定关键词报告 |
| KeywordCorrelation | `idx_corr_keyword` on (keyword_id_a, keyword_id_b) | 查询关键词关联 |

---

## LLM 配置项

在 `.env` / `config.py` 中新增：

```
# LLM 服务配置
LLM_PROVIDER=openai_compatible    # 统一用 OpenAI compatible API 格式
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=sk-xxx

# 三级模型
LLM_TIER1_MODEL=qwen-turbo
LLM_TIER2_MODEL=qwen-plus
LLM_TIER3_MODEL=qwen-max

# 调用控制
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
LLM_BATCH_SIZE=20
LLM_CIRCUIT_BREAKER_THRESHOLD=5
```

---

## 设计原则

1. **规则优先，LLM 兜底** — 能用计算解决的不用 LLM
2. **核心链路不省** — 关键词匹配准确率直接决定产品价值，用 Tier 2 模型保证效果
3. **批量调用** — 所有 LLM 调用都是批量（20-30 篇/次），不逐篇调用
4. **可降级** — Tier 2 失败可降级到 Tier 1，LLM 全挂可回退到纯规则匹配
5. **配置化** — 模型、阈值、评分权重均通过配置管理，不硬编码
