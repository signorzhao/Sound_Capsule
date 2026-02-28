---
name: ServiceRole最小化改造
overview: 将 service_role 从用户端回收至可信后端，采用最小变更路径先止血再切换大文件上传为签名直传，降低安全与性能风险并保持功能连续性。
todos:
  - id: rotate-service-role
    content: 轮换 service_role 并在客户端禁用默认回退
    status: completed
  - id: strict-sidecar-config
    content: sidecar 启动改为缺失密钥即失败，去除硬编码默认值
    status: completed
  - id: thin-admin-proxy
    content: 梳理并收口高权限接口到后端薄代理
    status: completed
  - id: signed-upload-endpoint
    content: 新增签名上传 URL 接口并接入鉴权
    status: completed
  - id: frontend-direct-upload-switch
    content: 前端接入签名直传并保留回退开关
    status: completed
  - id: regression-and-observability
    content: 执行回归测试与上传链路监控验收
    status: completed
  - id: minimal-e2e-alignment
    content: 按现有服务端接口完成一次最小联调闭环并记录差异
    status: completed
  - id: tags-cors-hardening-decision
    content: 决策并排期 tags 写入补齐与 CORS 收紧
    status: completed
  - id: client-integration-gates
    content: 以客户端对接 Checklist 作为执行门禁与上线前硬验收
    status: completed
isProject: false
---

# ServiceRole 回收最小改造计划

## 目标与边界

- 目标：客户端不再持有 `SUPABASE_SERVICE_ROLE_KEY`，高权限操作仅在后端执行；大文件上传改为签名直传，避免 Python 中转带宽瓶颈。
- 边界：保留现有业务接口语义与前端交互，采用灰度与回退开关，避免一次性重构。

## 现状核对（与方案一致/冲突点）

- 客户端存在高风险回退：`[webapp/src-tauri/src/sidecar.rs](/Users/ianzhao/Desktop/Sound_Capsule/synesth/webapp/src-tauri/src/sidecar.rs)` 内置默认 `service_role`，并注入给 sidecar 进程。
- Python 侧统一用 `service_role` 访问 Supabase：`[data-pipeline/supabase_client.py](/Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/supabase_client.py)`。
- 当前大文件上传经 Python 中转（读取文件字节后上传），存在性能与内存压力：`[data-pipeline/capsule_api.py](/Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/capsule_api.py)`、`[data-pipeline/sync_service.py](/Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/sync_service.py)`。
- 前端未直接使用 supabase-js（有利于最小改造）。

## 服务端现状纳入（你提供的联调事实）

- `service_role` 已在服务端读取使用（不在浏览器前端直接使用），并支持 Bearer token 在线校验，且拒绝客户端传 `service_role token`（403）。
- 高权限代理 `/api/admin/rest/<path>` 仍在，存在表名/方法/limit 白名单逻辑，可作为过渡期薄代理承载点。
- 云端上传 `/api/cloud/upload-capsule` 仍在，具备 owner 校验；但当前不写 `cloud_capsule_tags`（仅 `cloud_capsules + Storage`）。
- 同步链路存在新旧双语义：`/api/sync/lightweight-page`（分页拉取） + `/api/sync/apply-lightweight-page`（本地落库）+ 兼容 `/api/sync/lightweight`。
- CORS 当前较宽（`/api/*` 允许 `origins="*"`），联调友好但生产需收紧。
- 环境变量完整性是联调与安全前置条件：`SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`、`ADMIN_ALLOWED_TABLES` 等必须齐全且环境一致。

## Key 职责矩阵（统一口径）

- `SUPABASE_SERVICE_ROLE_KEY`
  - 仅服务端持有与使用（可信后端环境）。
  - 用途：`/api/admin/rest/*` 高权限代理、跨用户/管理写入、签名 URL 签发、同步管理能力。
  - 禁止：客户端代码、客户端配置、客户端运行进程环境、打包产物中出现。
- `SUPABASE_ANON_KEY`
  - 可在客户端持有，仅用于低权限、RLS 可控的直连场景。
  - 不承载高权限写入与管理代理逻辑。
  - 作为补充能力，不替代轻量同步和上传主链路。
- `USER_ACCESS_TOKEN`（Bearer）
  - 客户端访问受保护接口的唯一身份凭证。
  - 后端先验 token，再决定是否代用 service_role 执行。

## 分阶段执行

### Phase 0：安全止血（先做）

- 轮换 Supabase `service_role`。
- 禁用客户端硬编码回退：sidecar 启动时若缺少配置，直接失败并提示，不使用默认 key。
- 将 `service_role` 仅放入受控后端环境（非用户设备分发文件）。
- 校验服务端“拒绝 service_role token”与白名单策略在生产配置仍生效（防回退）。

### Phase 1：最小联调闭环（先验证可用性，再改造）

- 按当前已可用后端能力执行一次固定顺序联调：登录 -> `admin/rest` 读 -> `upload-capsule` -> `lightweight-page` -> `apply-lightweight-page`。
- 输出“接口语义对照单”：请求头、鉴权方式、返回字段（`items/next_cursor`、本地落库计数）与失败码处理约定。
- 保留旧 `/api/sync/lightweight` 作为过渡回退路径，仅在新链路失败时启用并记录告警。
- 联调期间暂不改大架构，先确保功能稳定与错误可观测。
- 明确主链路归属：
  - 轻量同步主链路：云端 `lightweight-page` + 本地 sidecar `apply-lightweight-page`。
  - REAPER 胶囊本地保存不依赖 anon；云端上传走后端鉴权链路。

### Phase 2：高权限路径收口（薄代理）

- 保留现有前端请求入口，新增/收敛薄后端接口：仅做身份校验 + 代执行高权限 Supabase 操作。
- 前端侧仅传用户 token，不再传/持有高权限密钥。
- 优先迁移高风险能力：用户映射、跨用户查询、管理写入、同步管理端点。
- 将现有 `/api/admin/rest/<path>` 白名单能力作为承载基础，减少新增接口数量，控制变更面。

### Phase 3：Storage 改为签名直传（最小性能改造）

- 新增后端签名接口：输入对象路径与操作类型，返回短时上传 URL。
- 前端拿 URL 后直传到 Storage；Python 不再中转大文件字节。
- 元数据写入与标签同步仍由后端负责，保证鉴权闭环。
- 明确 `upload-capsule` 与 tags 语义：补齐 tags 写入（或增加独立 tags 同步步骤）后再切全量。
- 约束：即使引入 signed URL，权限判定仍由后端承担，客户端不直接持有 service_role。

### Phase 4：灰度与回退

- 增加特性开关：`direct_upload_signed_url`。
- 灰度阶段：直传失败自动回退旧上传链路，确保可用性。
- 观测指标：上传成功率、平均耗时、重试率、sidecar 内存峰值。
- 在灰度结束后收紧 CORS（从 `*` 到受控来源），并在预发先完成跨域回归。

## 验收与回归清单

- 安全：客户端二进制与配置中无 `service_role`；缺配置时启动失败而非回退默认值。
- 功能：登录、导出、胶囊上传、关键词同步、轻量同步全流程通过。
- 语义：`upload-capsule` 与 `cloud_capsule_tags` 行为一致（避免“上传成功但 tags 未落云”）。
- 性能：大文件上传耗时下降，sidecar 资源占用下降。
- 可回退：开关关闭可回到旧链路，不影响核心功能。

## 客户端对接门禁（按你提供的 Checklist 固化）

### P0 安全门禁（未满足不进入联调）

- 客户端代码与打包产物不含 `SUPABASE_SERVICE_ROLE_KEY`。
- 客户端仅持有 `SUPABASE_URL + ANON_KEY + USER_ACCESS_TOKEN`。
- 服务端配置完整：`SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`、`ADMIN_ALLOWED_TABLES`、`ADMIN_MAX_LIMIT`。
- key 使用符合职责矩阵：service_role 只在后端；anon 不承载高权限。
- 环境地址基线固定：
  - `VITE_LOCAL_API_ORIGIN=http://127.0.0.1:5003`
  - `VITE_CLOUD_API_ORIGIN=http://192.168.31.71:5002`
  - 判定规则：仅当同机同端口监听（如本机两个进程都占用 5002）才是端口冲突；`127.0.0.1:5003` 与 `192.168.31.71:5002` 不冲突。

### P1 接口与鉴权门禁

- 基础路由统一：`/api/auth/*`、`/api/admin/rest/*`、`/api/cloud/upload-capsule`、`/api/sync/lightweight-page`、`/api/sync/apply-lightweight-page`。
- 受保护接口统一 `Authorization: Bearer <USER_ACCESS_TOKEN>` 与 `Content-Type: application/json`。
- 会话策略统一：`401/403` 触发刷新或登出；刷新失败强制 `logout()`。

### P1 同步语义门禁（关键）

- 分页拉取 `lightweight-page`，以 `next_cursor` 循环结束条件为准。
- 每页 `items` 立即提交 `apply-lightweight-page`。
- 统计以本地 apply 结果（`inserted/updated/skipped/preview_downloaded`）为准，禁止仅凭云端 `skipped_count` 判定完成。
- `207` 视为部分成功：提示可重试但不中断整轮策略。
- 轻量同步优先后端主链路，anon 仅可作为补充读能力，不替代主链路。

### P2 上传与标签语义门禁

- `upload-capsule` 返回值解析固定：`cloud_id` 与 `storage.uploaded/errors`。
- 明确当前限制：`upload-capsule` 不写 tags；标签必须走独立同步链路。
- 在“tags 补齐”落地前，前端提示与状态图标语义需与此一致，避免“上传成功但标签缺失”误判。
- REAPER 胶囊本地保存不依赖 anon；云端上传鉴权与权限边界由后端承担。
- 对接最新契约：
  - 鉴权固定：`Authorization: Bearer <USER_ACCESS_TOKEN>`。
  - `tags/coordinates` 双来源兼容：优先顶层 `request.tags/request.coordinates`，缺失时回退 `request.capsule.tags/request.capsule.coordinates`。
  - 成功判定需同时检查：`success=true`、`cloud_id` 存在、`data.storage.errors` 为空；若包含同步信息则校验 `data.sync.tags_uploaded/coordinates_uploaded`。

### P2 本地一致性与联调闭环

- 切换导出目录时提示是否清理本地 SQLite 缓存（保留表结构）。
- 首次联调前执行一次本地缓存清理，避免历史数据干扰。
- 最小闭环：登录 -> admin/rest 读 -> upload-capsule -> lightweight-page/apply -> 本地云端数量与关键词一致。

### 上线前门禁

- 生产 CORS 从 `origins="*"` 收紧到真实来源。
- 服务器日志可按 `request_id` 串联问题链路。
- 覆盖 `400/401/403/207/5xx` 的前端错误语义提示与重试策略。

## Phase 1 标准联调 Runbook（固定顺序）

以下步骤作为“最小联调闭环”标准执行脚本，任何环境迁移或回归都按此顺序执行并记录结果：

1. 变量准备：`API_ORIGIN/API_BASE/LOGIN_EMAIL/LOGIN_PASSWORD`。
  - 默认云端：`API_ORIGIN=http://192.168.31.71:5002`
  - 默认本地：`LOCAL_API_BASE=http://127.0.0.1:5003/api`
2. 健康检查：`GET /api/health`（期望 `success=true`）。
3. 登录取 token：`POST /api/auth/login`，提取 `access_token/refresh_token`（长度 > 0）。
4. 会话验证：`GET /api/auth/me`（Bearer access token）。
5. 管理代理读取：`GET /api/admin/rest/cloud_capsules?...&limit=5`（若 403/400 检查 `ADMIN_ALLOWED_TABLES/ADMIN_MAX_LIMIT`）。
6. 云端分页拉取：`POST /api/sync/lightweight-page`（取 `items/next_cursor`）。
7. 本地应用一页：`POST local /api/sync/apply-lightweight-page`（统计以本地 apply 返回为准）。
8. 翻页循环：继续 `lightweight-page` 直到 `next_cursor=null`。
9. 上传冒烟：`POST /api/cloud/upload-capsule`（结构验证，返回 `cloud_id`；注意该接口当前不写 tags）。
10. 刷新验证：`POST /api/auth/refresh`（返回新 token）。
11. 失败语义回归：覆盖 `401/400(limit/cursor)/5xx(+request_id)`。

### upload-capsule 最新契约（客户端实现基线）

- 请求体关键结构：
  - `capsule`（名称、路径、类型、metadata）。
  - `files`（`preview`、`rpp`、`audio[]`，base64 内容）。
  - `tags/coordinates` 支持顶层与 `capsule` 内双来源（按“顶层优先，capsule 回退”解析）。
- 响应体关键结构：
  - 顶层：`success`、`cloud_id`、`error`。
  - `data.sync`：`uploaded/errors/tags_uploaded/coordinates_uploaded`。
  - `data.storage`：`uploaded/errors`（含 preview、rpp、audio_folder 统计）。
- 客户端兼容策略：
  - 旧版服务端缺失 `data.sync` 字段时不报错，按 `success/cloud_id/storage.errors` 判定主流程。
  - 新版服务端存在 `data.sync` 时，将 `tags_uploaded/coordinates_uploaded` 纳入 UI 反馈与日志埋点。

### 执行要求

- 每一步都记录“请求、状态码、核心响应字段、request_id（若有）”。
- 轻量同步阶段必须记录“云端分页计数”和“本地 apply 计数”两套指标，禁止混用判断完成状态。
- `upload-capsule` 阶段单独记录“capsule 上传成功”与“tags 是否已同步”两条结论，避免语义误判。

## 关键文件与变更焦点

- `[webapp/src-tauri/src/sidecar.rs](/Users/ianzhao/Desktop/Sound_Capsule/synesth/webapp/src-tauri/src/sidecar.rs)`：移除默认 key 回退、严格读取受控配置。
- `[data-pipeline/supabase_client.py](/Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/supabase_client.py)`：保留后端高权限调用；补签名 URL 能力接口封装。
- `[data-pipeline/capsule_api.py](/Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/capsule_api.py)`：新增签名 URL 端点与鉴权。
- `[data-pipeline/sync_service.py](/Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/sync_service.py)`：上传流程改为“签名直传优先 + 失败回退”。
- `[data-pipeline/routes/sync_routes.py](/Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/routes/sync_routes.py)`：固化 `lightweight-page/apply-lightweight-page` 新语义与错误处理约定。
- `[data-pipeline/routes/library_routes.py](/Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/routes/library_routes.py)`：确保胶囊/关键词状态与云端 tags 落库语义一致。

