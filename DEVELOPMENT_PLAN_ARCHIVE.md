# XMind AI Planner 开发计划归档（纯 AI 连续执行版）

## 1. 目标与范围

本项目从零开始实现，参考既有需求与设计文档的功能节奏，按“任务队列持续运行直到全部完成”的方式推进。

- 需求基线：`REQUIREMENTS.md`
- 设计基线：`DESIGN.md`
- 执行方式：纯 AI 自动化任务循环，不设人工排班节奏

## 2. 执行原则

1. 仅按依赖关系推进，未满足依赖的任务不得启动。
2. 每次只推进一个“开发中”任务，避免并发改动互相阻塞。
3. 任务完成必须同时满足：代码变更、测试通过、验收记录更新。
4. 失败任务可重试，连续失败转 `need_confirm`，确认后再继续。
5. 所有任务完成后进行一次全量回归与发布检查，方可收官。

## 3. 里程碑与任务拆解

### M0 基座搭建

| ID | 任务 | 依赖 |
|---|---|---|
| BOOT-01 | 初始化目录结构（backend/frontend/tests/scripts/docs） | - |
| BOOT-02 | FastAPI 应用骨架与路由分层 | BOOT-01 |
| BOOT-03 | 前端原生 JS 页面骨架与 MindElixir 挂载 | BOOT-01 |
| BOOT-04 | SQLite 与迁移框架 | BOOT-02 |
| BOOT-05 | 配置中心与环境变量加载 | BOOT-02 |
| BOOT-06 | 日志、错误码、全局异常处理 | BOOT-02 |
| BOOT-07 | CI 流水线（lint/test/build） | BOOT-01 |
| BOOT-08 | 自动化任务执行器最小闭环 | BOOT-07 |

### M1 核心脑图能力（v2.0 基线）

| ID | 任务 | 依赖 |
|---|---|---|
| CORE-01 | Node 数据模型与 MindElixir 转换层 | BOOT-03 |
| CORE-02 | 基础编辑（增删改/折叠/缩放/拖动画布） | CORE-01 |
| CORE-03 | AI 生成初始结构/展开子节点/重写节点 | BOOT-05 |
| CORE-04 | Markdown 导出 | CORE-01 |
| CORE-05 | Word 导出（python-docx） | CORE-04 |
| CORE-06 | 本地离线资源部署（无外网可运行） | CORE-02 |
| CORE-07 | 核心 E2E 回归（编辑+AI+导出） | CORE-02,CORE-03,CORE-05 |

### M2 文档系统与工作区（v2.1~v2.4）

| ID | 任务 | 依赖 |
|---|---|---|
| DOC-01 | 文档 CRUD（UUID/owner/软删） | BOOT-04 |
| DOC-02 | 分享链接创建与可编辑分享页 | DOC-01 |
| IMP-01 | Markdown 导入 | DOC-01 |
| IMP-02 | 增量合并导入（AI 定位） | IMP-01 |
| IMP-03 | 批量目录导入 | IMP-01 |
| AUTH-01 | 工号登录/JWT/Cookie | BOOT-04 |
| AUTH-02 | RBAC（admin/reviewer/employee） | AUTH-01 |
| AUTH-03 | 用户管理（仅 admin） | AUTH-02 |
| WS-01 | 个人工作区与文档列表页 | DOC-01,AUTH-01 |

### M3 协作与治理（v2.5~v2.9）

| ID | 任务 | 依赖 |
|---|---|---|
| VER-01 | 版本历史记录（最多 50） | DOC-01 |
| VER-02 | 版本列表/预览/回滚 | VER-01 |
| PROJ-01 | 项目工作区 CRUD 与成员管理 | AUTH-02 |
| PROJ-02 | 文档在个人/项目工作区间移动 | PROJ-01 |
| RT-01 | WebSocket 连接管理与重连心跳 | DOC-01 |
| RT-02 | 2 秒防抖自动保存与广播同步 | RT-01 |
| LOCK-01 | 节点锁定（占用/释放/冲突提示） | RT-02 |
| REVIEW-01 | 待审核变更模型与接口 | AUTH-02,RT-02 |
| REVIEW-02 | 审核面板（通过/拒绝/批量） | REVIEW-01 |

### M4 Agent 与自动化闭环（v3.1~v3.3.2）

| ID | 任务 | 依赖 |
|---|---|---|
| AG-01 | Agent 面板 UI（Cursor 风格） | CORE-02 |
| AG-02 | 对话/消息/节点修改表与 API | AG-01,BOOT-04 |
| AG-03 | Diff 展示与 Keep/Undo（单条+批量） | AG-02 |
| AG-04 | SSE 流式响应与非流式回退 | AG-02 |
| AG-05 | 节点 ID 上下文约束与解析增强 | AG-03 |
| AUTO-01 | 任务队列 + 状态机（waiting 到 done） | BOOT-08 |
| AUTO-02 | need_confirm 规则引擎 | AUTO-01 |
| AUTO-03 | Artifacts（conversation/diff/patch/manifest） | AUTO-01 |
| AUTO-04 | 提交工作区、合并包、清理 | AUTO-03 |
| FILE-01 | 文件目录树（懒加载/过滤规则） | PROJ-01 |
| FILE-02 | 文件/文件夹添加为节点（fileRef） | FILE-01 |
| FILE-03 | MD 文件编辑器（复用 Vditor） | FILE-02 |
| FILE-04 | 脑图关联（绑定/导出新脑图/收回/解除） | FILE-02 |

### M5 收尾与增强（待实现项 + 远期项）

| ID | 任务 | 依赖 |
|---|---|---|
| GAP-01 | 撤销/重做（含 Ctrl+Z/Ctrl+Y） | CORE-02 |
| GAP-02 | 节点拖拽排序（同级/跨父级） | CORE-02 |
| GAP-03 | 手动保存/加载 JSON | DOC-01 |
| GAP-04 | 导出 XMind | CORE-01 |
| GAP-05 | 导出 PNG/SVG | CORE-02 |
| GAP-06 | 云端同步（多端） | RT-02 |
| GAP-07 | 协作冲突处理升级（OT/CRDT） | GAP-06 |
| GAP-08 | 模板库（创建/应用） | DOC-01 |
| GAP-09 | AI 增强（续写/润色/翻译） | CORE-03 |
| REL-01 | 全量回归、压测、安全检查、发布演练 | M0~M5 全部完成 |

## 4. 统一验收标准（DoD）

每个任务完成必须满足全部条件：

1. 功能实现与需求一致。
2. 单元测试与必要的集成测试通过。
3. 无阻断级构建错误或 lint 错误。
4. 任务状态与产物记录（变更说明、测试结果）已更新。

## 5. 完成判定

当且仅当以下条件同时满足，项目视为完成：

1. M0~M5 所有任务状态为 `done`。
2. `REL-01` 完成并通过。
3. 不存在 `need_confirm` 未处理项与 `failed` 任务。
