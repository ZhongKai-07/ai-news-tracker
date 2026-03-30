# V2 数据智能升级 — 执行策略

**日期**：2026-03-30
**关联文档**：
- 设计文档：`docs/superpowers/specs/2026-03-30-v2-data-intelligence-design.md`
- 实施计划：`docs/superpowers/plans/2026-03-30-v2-data-intelligence.md`

---

## 核心原则

每个 Chunk 是一个可独立验证的里程碑，不要跨 Chunk 带着未解决的问题往前走。

---

## 执行方式：按 Chunk 分会话

每个 Chunk 用一个独立的 Claude Code 会话执行。原因：
- 上下文窗口有限，24 个 Task 全塞进一个会话，后半段的代码质量会下降
- 每个 Chunk 结束后可以自己跑一遍、手动验证，发现问题就地修
- 出了问题回滚范围小，只回退一个 Chunk 而不是全部

---

## Chunk 间的验收检查点

每个 Chunk 完成后，执行以下检查再进入下一个：

| 检查 | 命令 |
|------|------|
| 全量后端测试通过 | `cd backend && python -m pytest tests/ -v` |
| 无未提交的改动 | `git status` |
| 服务能正常启动 | `python -m uvicorn app.main:app --port 8001` |
| 前端能编译（Chunk 5 后）| `cd frontend && npm run build` |

---

## 风险评估与注意事项

### Chunk 2-3：最大风险区（改核心爬虫链路）

- **Task 8（改 crawler.py 的 `_process_article`）**：
  - 开始前先在本地跑一次完整爬取流程，确认当前系统正常（回归基线）
  - 完成后不光跑测试，还要手动触发一次爬取，检查数据库新字段是否如预期填充
  - 改动量不大，出问题容易 `git diff` 定位

### Chunk 3：LLM 集成需要真实 API 验证

- Task 11 的 LLM process job 测试中用的是 mock
- 上线前必须用真实 API 验证一次：
  1. 配好 `.env` 里的 `LLM_BASE_URL` 和 `LLM_API_KEY`
  2. 手动调用 `run_llm_process()` 看返回格式
  3. LLM 返回的 JSON 格式经常不严格（多余的 markdown 包裹、字段名不一致），这部分最容易出问题

---

## 执行顺序与预估

| 顺序 | Chunk | 内容 | Tasks | 会话数 | 关键注意 |
|------|-------|------|-------|--------|---------|
| 第 1 天 | Chunk 1 | 基础建设：DB 模型、Config、LLM 服务、Alembic | 1-5 | 1 | 最平稳，纯新增 |
| 第 2 天 | Chunk 2 | 数据清洗管道：HTML净化、质量评分、摘要 | 6-8 | 1 | Task 8 改 crawler 要小心 |
| 第 3 天 | Chunk 3 | 语义匹配 + LLM 定时 Job | 9-11 | 1 | 需要真实 LLM API 验证 |
| 第 4 天 | Chunk 4 | 深度分析：预警、趋势报告、关联 | 12-15 | 1 | 相对独立，风险低 |
| 第 5 天 | Chunk 5 | API 端点 + 前端页面 | 16-22 | 1-2 | 前端改动多，可能需要调 UI |
| 第 6 天 | Chunk 6 | 集成测试 + 端到端验证 | 23-24 | 1 | 完整链路跑通 |

---

## 退路机制

### Git Tag 保护

每个 Chunk 开始前打一个 tag：

```bash
git tag v2-before-chunk-1
git tag v2-before-chunk-2
# ...以此类推
```

### 回滚策略

- 每个 Task 都有独立 commit，可以 `git log` 找到最后一个好的状态
- 最坏情况回退到 Chunk 开始前的 tag，损失最多一个 Chunk 的工作量
- 回退命令：`git reset --hard v2-before-chunk-N`

---

## 进度追踪

| Chunk | 状态 | 开始日期 | 完成日期 | 备注 |
|-------|------|----------|----------|------|
| 1 | 待开始 | | | |
| 2 | 待开始 | | | |
| 3 | 待开始 | | | |
| 4 | 待开始 | | | |
| 5 | 待开始 | | | |
| 6 | 待开始 | | | |
