# Sound Capsule 私有化部署资料

本目录是 **Sound Capsule 自建 Supabase** 的部署资料夹，包含从安装 Docker、执行 SQL 到客户端配置的一整套文档与脚本。按推荐顺序使用即可完成部署与迁移。

---

## 推荐阅读顺序

| 场景 | 文档 | 说明 |
|------|------|------|
| **首次部署** | [Sound Capsule 私有化 Supabase 完整部署指南](./Sound_Capsule_私有化Supabase_完整部署指南.md) | 从环境准备到验证的一站式步骤 |
| **迁移/复用** | [私有化 Supabase 快速复用部署指南](./私有化Supabase_快速复用部署指南.md) | 备份、恢复、换机迁移 |
| **检查清单** | [部署说明](./部署说明.md) | 按步骤勾选，避免遗漏 |
| **SQL 顺序** | [database/执行顺序.md](./database/执行顺序.md) | 建表与 Storage 策略的执行顺序（含 **007 上传策略必做**） |

更多细节（Auth 取消邮件验证、Storage 策略说明、故障排查）见项目根目录 **[docs/SUPABASE_PRIVATE_DEPLOY.md](../SUPABASE_PRIVATE_DEPLOY.md)**。  
应用更新记录见 **[docs/应用更新记录.md](../应用更新记录.md)**。

---

## 核心要点（成功经验）

1. **Storage 上传 403 /「文件上传不完整」**  
   自建 Supabase 必须为 `capsule-files` 配置 **INSERT** 策略。`001_add_global_read_policies.sql` 只包含 **SELECT**，不包含 INSERT。  
   → 执行 **`database/007_storage_capsule_files_allow_authenticated_upload.sql`**（或按 [SUPABASE_PRIVATE_DEPLOY.md](../SUPABASE_PRIVATE_DEPLOY.md) 中的 SQL 手动添加）。

2. **SQL 执行顺序**  
   本目录 `database/` 下为 **001～007** 共 7 个文件，按编号顺序执行即可。详见 [database/执行顺序.md](./database/执行顺序.md)。

3. **客户端配置**  
   `data-pipeline/.env.supabase` 或桌面端配置目录下的 `.env.supabase` 中填写 `SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`，且 URL 需带 `http://` 或 `https://`。

---

## 目录结构

| 路径 | 说明 |
|------|------|
| **Sound_Capsule_私有化Supabase_完整部署指南.md** | 完整部署步骤（推荐首读） |
| **私有化Supabase_快速复用部署指南.md** | 迁移、备份、恢复 |
| **部署说明.md** | 部署检查清单 |
| **传输说明.md** | 本目录内容说明与跨机使用方式 |
| **database/** | SQL 脚本与执行顺序说明；含 **007**（Storage 上传策略） |
| **deploy-supabase.sh** | 首次部署脚本 |
| **backup-supabase.sh** / **restore-supabase.sh** | 备份与恢复脚本 |
| **docker-compose.yml** 等 | Supabase Docker 编排；可选参考 **CHANGELOG.md**、**versions.md**（上游版本记录） |

---

## 快速检查

- [ ] 已按 [执行顺序.md](./database/执行顺序.md) 执行 SQL 1～7（其中 **007 必做**）
- [ ] 已创建私有 bucket `capsule-files` 并已执行 007（或手动添加 INSERT 策略）
- [ ] 客户端已配置 `.env.supabase`（URL + Service Role Key）
- [ ] 若上传仍 403，先确认已执行 007 或 [SUPABASE_PRIVATE_DEPLOY.md](../SUPABASE_PRIVATE_DEPLOY.md) 中的 INSERT 策略
