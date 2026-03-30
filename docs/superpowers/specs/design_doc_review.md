这份设计文档整体结构清晰、业务目标明确，技术选型（FastAPI + React + SQLite/PG + asyncio）非常务实且贴合需求。针对 IO 密集型的并发抓取场景，这种渐进式演进的轻量级架构能够保证极快的初期交付速度，同时预留了部署升级的空间。数据模型中设计的 `TrendSnapshot` 预聚合机制也非常亮眼，能有效保障前端大跨度时间查询的响应性能。

作为一个资深系统架构师，我从**系统健壮性、多进程并发、数据一致性以及扩展性**的角度对该文档进行 Review，并提出以下潜在风险与改进建议：

**架构风险与改进建议**

- **多进程部署下的并发锁与调度失效**
  当前设计依赖内存级的 `asyncio.Lock` 作为防并发锁，并将 APScheduler 嵌入在 FastAPI 应用中。这在本地单进程（SQLite）开发时没有问题，但在生产环境（PostgreSQL）中，FastAPI 通常会通过 Gunicorn/Uvicorn 启动多个 Worker 进程。此时内存锁和调度器都是进程隔离的，会导致**同一时刻触发多次相同的抓取任务**。
  - **建议**：若系统必须支持多 Worker 部署，需将 APScheduler 的 JobStore 切换为 SQLAlchemyJobStore 并开启数据库级别的悲观锁（如 `SELECT ... FOR UPDATE`）。更优雅的做法是将 API 服务与爬虫调度彻底解耦，API 仅负责写库，由单一的后台守护进程（或 Celery/ARQ）专门负责执行 APScheduler 和爬虫任务。

- **写入时匹配（Write-time Matching）的场景缺失**
  文档设定“关键词匹配在文章抓取入库时执行”。这会带来一个致命的业务盲区：当用户**添加新关键词**或**为现有关键词增加新别名**时，系统无法从已入库的历史文章中追溯这些词，导致新词的历史趋势图为空。
  - **建议**：补充“历史数据重算（Backfill/Rescan）”机制。在新增或修改关键词时，提供一个后台异步任务接口（如 `POST /api/keywords/{id}/rescan`），对数据库中现有的 `Article` 进行一次增量匹配，重新生成 `KeywordMention` 和 `TrendSnapshot`。

- **反爬策略与容错机制不足**
  科技媒体（如 InfoQ、Reddit、知乎）通常具备严格的 WAF 或反爬策略。文档中仅使用了 `asyncio.Semaphore` 控制并发，这无法解决 IP 被封禁的问题。
  - **建议**：在 `DataSource` 模型中预留代理配置（Proxy URL）和自定义 HTTP Headers 的字段。同时，针对 `consecutive_failures`（连续失败）机制，建议引入**指数退避（Exponential Backoff）**策略，当错误达到阈值时自动降低该源的抓取频率，避免被目标网站永久拉黑。

- **系统鉴权与公网暴露风险**
  文档未提及用户认证机制。如果是纯本地运行无妨，但既然考虑了 PostgreSQL 部署，一旦暴露在公网，任何人都可以调用 `POST /api/crawl/trigger` 触发全量抓取，这极易引发 DDoS 效应耗尽服务器资源。
  - **建议**：明确系统的部署边界。若包含公网部署计划，需在 FastAPI 层引入基础鉴权（如基于中间件的 API Token 校验或 JWT 登录机制），并为高耗时 API 增加 Rate Limiting。

**数据模型与细节优化**

- **明确时区边界（Timezone Consistency）**
  `TrendSnapshot` 采用日期粒度（date）进行聚合。如果没有严格的时区规范，服务器时区与前端用户时区的差异会导致热力图数据在午夜发生“漂移”。
  - **建议**：架构层面强制规定后端所有的时间戳和日期聚合均使用 UTC 时间。前端请求数据后，再根据本地浏览器时区进行偏移渲染。

- **引入软删除（Soft Delete）**
  设计中包含了 `DELETE /api/keywords/{id}`。在关系型数据库中，直接物理删除关键词可能会级联删除大量的 `KeywordMention` 和历史 `TrendSnapshot`。若用户误删，恢复成本极高。
  - **建议**：为 `Keyword` 表引入 `is_active` 或 `deleted_at` 字段实现软删除。前端列表默认过滤掉已删除的关键词即可。

- **文章数据的生命周期管理（Data Retention）**
  爬虫系统的数据膨胀速度极快，长期运行会导致 `Article` 表的 `content` 字段占据巨量磁盘空间。
  - **建议**：设计数据清理或冷热分离策略。例如：增加一个定时清理任务，仅保留最近 90 天的 `content` 正文，90 天前的历史文章只保留 `title`、`url` 和已生成的命中记录，从而大幅降低数据库的存储压力。