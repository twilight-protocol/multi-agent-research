# 多智能体行业研究助手（MAR）

一个面向行业研究的多智能体（Multi-Agent）Web 应用：用户上传 PDF 资料或联网提问，系统通过 **LangGraph 编排的六节点研究流水线**，自动完成「检索 → 分析 → 撰写 → 自审 → 修订 → 人工终审」，并支持人工在终稿前介入修改。

---

## 1. 功能特性

- **双路检索**：支持「仅本地知识库（kb）」「仅联网（web）」「自动双路（both）」三种检索范围，按需调用本地向量库或 Tavily 联网搜索。
- **引用可追溯**：报告中的每条关键发现都会原样标注出处（`[文件名 第N页]` 或 `[web: url]`），杜绝无来源断言。
- **自审-修订闭环**：审稿节点只做审查、绝不重写，针对「断言无出处 / 出处不符 / 覆盖不足」三类硬问题给出可执行修改意见，由修订节点逐条落实。
- **人工终审（Human-in-the-loop）**：报告经自审后暂停，等待人工「通过」或「带意见退回」；断点落盘，跨请求可恢复。
- **多租户数据隔离**：基于 `X-User-Id` 请求头做数据归属——上传文件、向量库检索、会话线程均按用户分隔，互不串档。
- **流式进度**：后端以 SSE（Server-Sent Events）实时推送节点进度与终稿，前端可视化展示流水线运行状态。
- **检索评测脚本**：内置召回率评测工具，可量化阈值对召回率 / 误收率的影响（见 [§9](#9-检索评测)）。
- **生产级部署**：多阶段 Docker 镜像 + `docker-compose`，自带健康检查与异常自动重启。

---

## 2. 架构概览

### 研究流水线（LangGraph 六节点图）

```
        ┌─────────┐
START → │ search  │  双路检索（kb / web / both）
        └────┬────┘
             ↓
        ┌─────────┐
        │ analyze │  资料分析师：要点 / 矛盾 / 信息缺口
        └────┬────┘
             ↓
        ┌─────────┐
        │  write  │  研究员：结构化报告（概述 / 关键发现 / 结论）
        └────┬────┘
             ↓
        ┌─────────┐
        │critique │  审稿人：只审查，给出 issue 清单
        └────┬────┘
         verdict?│
   ┌──────────┼───────────────┐
  pass      revise          always-review
   │           ↓                 │
   │     ┌─────────┐             │
   │     │ revise  │ ←──┐        │
   │     └────┬────┘    │（未达上限）
   │          │ ────────┘        │
   │          ↓                  ↓
   │     ┌──────────────┐  ┌──────────────┐
   │     │（达上限/人审）│  │ human_review │ interrupt
   │     └──────────────┘  └──────┬───────┘
   │          │ approve / revise  │
   └─────────→└──────────────────→┘
                              ↓
                             END
```

- **路由规则**：`critique` 不通过且未达修订上限 → `revise`；通过且非强制人工 → `END`；否则 → `human_review`。
- **修订硬上限**：`MAX_REVISIONS`（默认 2）由代码兜底，防止审稿与修订无限振荡；人工介入后可再推动 `HUMAN_EXTRA_REVISIONS`（默认 1）次。

### 技术栈

| 层 | 选型 |
| --- | --- |
| 后端框架 | FastAPI + Uvicorn（单 worker） |
| 多智能体编排 | LangGraph（`StateGraph` + `AsyncSqliteSaver` 断点） |
| LLM / 向量模型 | 阿里云百炼 DashScope（`qwen-plus` / `text-embedding-v3`），OpenAI 兼容端点 |
| 向量库（RAG） | Chroma（`knowledge_base` 集合，持久化于 `data/chroma_db`） |
| 联网搜索 | Tavily |
| 前端 | Vue 3 + Vite（原生 SSE over POST 客户端，无额外依赖） |
| 部署 | Docker 多阶段构建 + docker-compose |

---

## 3. 目录结构

```
multi-agent-research/
├── backend/
│   ├── main.py                 # FastAPI 入口：路由挂载、StaticFiles、lifespan
│   ├── config.py               # 全部可配置项（从 .env 读取）
│   ├── identity.py             # X-User-Id 解析与格式校验
│   ├── ratelimit.py            # 基于 IP 的滑动窗口限流（研究 / 上传分别计额）
│   ├── ai/
│   │   ├── llm.py              # ChatOpenAI 实例（DashScope 兼容端点）
│   │   ├── vectorstore.py      # Chroma 连接与 embedding 封装
│   │   ├── ingest.py           # PDF 解析、切块、入库、孤儿文件清理
│   │   └── research/
│   │       ├── graph.py        # 六节点图构建与路由条件
│   │       ├── state.py        # ResearchState（图状态定义）
│   │       ├── node.py         # 各节点实现（search/analyze/write/critique/revise/human）
│   │       ├── tools.py        # web_search / fetch_url / search_local
│   │       └── service.py      # 图生命周期（AsyncSqliteSaver 持久化）
│   └── api/
│       ├── research.py         # /api/research/stream、/resume（SSE）
│       └── upload.py           # /api/upload（PDF 上传与入库）
├── frontend/
│   ├── index.html
│   ├── src/
│   │   ├── App.vue             # 主界面与事件处理
│   │   ├── api/{research,identity}.js
│   │   ├── components/         # NodeProgress / ReportView / ReviewCard / UploadPanel
│   │   └── utils/markdown.js   # Markdown 渲染
│   └── dist/                   # 构建产物（由 Docker 多阶段构建生成）
├── scripts/
│   ├── ingest_local.py         # 本地 PDF 灌库（需指定 user_id）
│   ├── run.py                  # 本地调试图（内存断点）
│   └── eval_retrieval.py       # 检索召回率评测 + 阈值曲线
├── data/
│   ├── app.db                  # SQLite：LangGraph 检查点（会话/线程）
│   ├── chroma_db/             # 向量库持久化目录
│   ├── uploads/               # 用户上传 PDF（按 user_id 分子目录）
│   └── seed/                  # 评测集与评测报告
├── Dockerfile / docker-compose.yml
├── requirements.txt
└── .env                       # 密钥与配置（不入库）
```

---

## 4. 本地开发

### 4.1 前置条件

- Python 3.14+
- Node.js 22+
- 有效的 DashScope API Key（对话 / embedding）与 Tavily API Key（联网搜索）

### 4.2 后端

```bash
# 1. 安装依赖（建议在虚拟环境中）
pip install -r requirements.txt

# 2. 准备 .env（参考下方「配置」章节）
cp .env.example .env   # 如没有示例，手动创建并填入密钥

# 3. 启动服务（监听 8000）
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1
```

> 注意：`workers` 必须设为 **1**，否则多进程的 SQLite 检查点无法共享，人工终审的断点恢复会失效。

### 4.3 前端

```bash
cd frontend
npm install
npm run dev        # 默认 Vite 开发服务器
```

开发模式下前端通过 `fetch` 直连后端；构建产物（`npm run build` → `dist/`）会被后端以 `StaticFiles` 挂载为兜底路由 `/`。

### 4.4 本地灌库与调试

```bash
# 将本地 PDF 灌入向量库（必须指定归属用户）
python -m scripts.ingest_local <pdf路径> <user_id>

# 本地跑一遍图（内存断点，无需数据库）
python -m scripts.run
```

---

## 5. 配置

所有配置项集中在 `backend/config.py`，可通过 `.env` 覆盖（**`.env` 已被 `.gitignore` 与 `.dockerignore` 排除，永不入库**）。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DASHSCOPE_API_KEY` | 必填 | 百炼对话 / 向量模型密钥 |
| `TAVILY_API_KEY` | 空 | 联网搜索密钥（仅 `web`/`both` 模式需要） |
| `LLM_MODEL` | `qwen-plus` | 对话模型名 |
| `EMBEDDING_MODEL` | `text-embedding-v3` | 向量模型名（**换模型必须重建向量库**） |
| `COLLECTION_NAME` | `knowledge_base` | Chroma 集合名 |
| `RAG_TOP_K` | `4` | 最终返回片段数上限 |
| `RAG_FETCH_K` | `8` | 向量库超取条数（where 后置过滤，先取后筛） |
| `MAX_DISTANCE` | `0.8` | 相似度阈值（score=2-2cos 的平方距离） |
| `EMBEDDING_BATCH_SIZE` | `10` | embedding 单批条数（DashScope 上限 10） |
| `WEB_SEARCH_MAX_RESULTS` | `5` | 联网搜索结果条数 |
| `WEB_FETCH_MAX_CHARS` | `4000` | 网页正文截断上限 |
| `WEB_FETCH_TIMEOUT` | `10` | 外部请求超时（秒） |
| `MAX_UPLOAD_MB` | `20` | 单文件上传上限（MB） |
| `MAX_UPLOAD_FILES` | `200` | 单用户文件数上限 |
| `MAX_UPLOAD_TOTAL_MB` | `1024` | 单用户存储总量上限（MB） |
| `MAX_REVISIONS` | `2` | 自审-修订硬上限 |
| `HUMAN_REVIEW_MODE` | `always` | 自审通过后是否强制人工终审 |
| `HUMAN_EXTRA_REVISIONS` | `1` | 人工介入后可额外推动的修订次数 |
| `ORPHAN_CLEANUP_ON_START` | `true` | 启动时清理向量库已不再引用的孤儿 PDF |
| `RESEARCH_RATE_LIMIT_MAX` / `_WINDOW` | `5` / `60` | 研究接口限流（次 / 秒） |
| `UPLOAD_RATE_LIMIT_MAX` / `_WINDOW` | `3` / `60` | 上传接口限流（次 / 秒） |

---

## 6. Docker 部署

`Dockerfile` 采用多阶段构建：第一阶段用 `node:22-alpine` 构建前端 `dist`；第二阶段基于 `python:3.14-slim` 装配后端，并直接使用阿里云 PyPI 镜像加速装包。

```bash
# 构建并启动（对外端口 8001，容器内固定 8000）
docker compose up -d --build
```

- **端口**：`docker-compose.yml` 中 `8001:8000`，左侧为对外端口，可按需修改。
- **密钥**：通过 `env_file: .env` 注入容器，**不进镜像**。
- **数据持久化**：`./data` 挂载到容器内 `/app/data`，重启不丢数据。
- **健康检查**：`/health` 探活，启动宽限期 60s（图编译 + 建库比普通服务慢），失败自动 `restart: unless-stopped`。

---

## 7. 使用流程

1. **首次访问**：前端自动生成匿名用户标识并存入 `localStorage`，后续请求通过 `X-User-Id` 头带上（仅作数据归属，**非登录鉴权**，见 [§10](#10-安全与隔离说明)）。
2. **喂资料**（可选）：在左侧「上传面板」上传 PDF，系统解析切块后写入你的专属向量子库。
3. **选范围 + 提问**：选择检索范围（`仅知识库` / `仅联网` / `自动双路`），输入行业研究问题，点击「开始研究」。
4. **实时进度**：右侧实时显示节点进度（检索 / 分析 / 撰写 / 自审 / 修订 / 等待终审）。
5. **人工终审**：自审通过后进入待审状态，可「通过」发布，或「带修改意见退回」让 AI 再修订一轮。
6. **获取报告**：报告含概述、带引用的关键发现、结论，并标注停止原因（`自审通过` / `达到修订上限`）。

---

## 8. API 说明

所有接口均要求请求头 `X-User-Id`（8~64 位字母/数字/`-`/`_`），缺失或非法返回 `400`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/research/stream` | 发起研究，请求体 `{question, thread_id?, scope}`；返回 SSE 流（`progress`/`interrupt`/`done`/`error`） |
| `POST` | `/api/research/resume` | 人工终审恢复，请求体 `{thread_id, action: approve|revise, comment?}`；同样返回 SSE 流 |
| `POST` | `/api/upload` | 上传 PDF（仅 `.pdf`，单文件 ≤ `MAX_UPLOAD_MB`），自动解析切块入库 |
| `GET`  | `/health` | 健康检查 |
| `GET`  | `/` | 前端静态页（生产环境由后端托管 `dist/`） |

**SSE 事件**：

- `progress`：`{node, label}` —— 节点进度。
- `interrupt`：`{type:"draft_review", draft, thread_id, ...}` —— 等待人工终审，前端据此渲染审阅卡片。
- `done`：`{thread_id, report, stop_reason, revision_count}` —— 终稿。
- `error`：`{detail}` —— 错误。

> 为何用 `fetch` 而非 `EventSource`：`EventSource` 仅支持 GET，而本后端接口均为 POST，故前端实现了 POST + 手动分帧的 SSE 客户端。

---

## 9. 检索评测

`scripts/eval_retrieval.py` 提供召回率评测，**只调 embedding、不调 LLM**，可反复低成本运行，且口径与线上 `search_local` 一致（先取 `RAG_FETCH_K` → 过阈值 → 截 `RAG_TOP_K`，并带 `filter={"user_id": …}`）。

```bash
python -m scripts.eval_retrieval
```

评测集位于 `data/seed/eval_set.csv`（30 条：抽取型 12 / 概述型 10 / 负样本 8），结果输出到 `data/seed/eval_report.md`。当前库（`source=test.pdf`，24 页 / 27 chunk）在阈值 `0.8` 下：

- **总召回率 90.9%**（抽取型 11/12，概述型 9/10）
- 负样本误收 1/8
- 平均返回 3.14 条，单条检索均值 0.164s

结论：阈值 `0.8` 在召回与误收之间取得较优平衡，也是当前线上默认值。

---

## 10. 安全与隔离说明

- **多租户隔离是「数据归属」而非「权限边界」**：`X-User-Id` 由客户端自报，修改即可冒充他人、读取他人数据。生产环境应替换为服务端签发并校验的凭证（如 JWT / Session）。
- **thread_id 前缀隔离**：后端将 `{user_id}:{raw}` 作为线程 ID，resume 时校验前缀，杜绝跨用户会话访问。
- **上传配额按用户计**：文件数、总存储量均按 `user_id` 维度限制，避免单用户打满磁盘影响他人。
- **孤儿文件清理**：重传同名 PDF 会先删旧 chunk 再入库，启动时扫描并删除向量库已不再引用的磁盘文件（带宽限期，保守跳过旧格式数据）。
- **密钥管理**：所有密钥仅从 `.env` 读取，禁止硬编码；`.env` 已被排除出镜像与版本库。

---

## 11. 已知限制

- 单实例设计：依赖 `workers=1` 与本机 SQLite，未做水平扩展与多副本共享存储。
- 人工终审为同步阻塞点：会话在 `interrupt` 期间挂起，依赖 SQLite 检查点恢复。
- 联网抓取无 JS 渲染：仅解析静态 HTML 正文，对重度 SPA 页面可能抓不到内容。
- 前端无独立路由/后端服务：生产环境由 FastAPI 直接托管 `dist/`。

---

## 12. 许可证

本项目为学习 / 演示用途，详见仓库内相关说明。
