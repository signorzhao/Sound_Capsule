# 私有化 Supabase 连接项目清单

本文档列出将 **自建/私有化 Supabase** 接入 Sound Capsule 项目所需的环境、SQL、Storage 与配置。

---

## 一、项目需要的 Supabase 配置

后端（data-pipeline）和 Tauri 启动的 Sidecar 都会使用下面两个变量：

| 变量名 | 说明 |
|--------|------|
| `SUPABASE_URL` | 自建 Supabase 的 API 地址，如 `https://your-supabase.example.com` |
| `SUPABASE_SERVICE_ROLE_KEY` | Service Role Key（后端用，可绕过 RLS） |

- **后端**：从 `data-pipeline/.env.supabase` 读取（见 `supabase_client.py`）。
- **桌面端**：Sidecar 启动 API 时会把 Supabase 配置通过环境变量传给子进程；若在 **配置目录** 下存在 `.env.supabase`，会优先使用该文件中的值，否则使用默认（原云端）配置。
- **锚点编辑器**：与后端共用同一配置。`anchor_editor_v2.py` 通过 `dal_cloud_prisms` → `get_supabase_client()` 连接 Supabase，读的也是 `data-pipeline/.env.supabase`。**因此只要把 `.env.supabase` 改成新服务器的 URL 和 Key，锚点编辑器的「同步到云端」也会指向新服务器。**

---

## 二、本地/配置目录下的 .env.supabase

**方式 A：开发时用 data-pipeline 下的文件**

在 `data-pipeline/.env.supabase` 中配置（不要提交到 Git）：

```env
SUPABASE_URL=https://your-supabase.example.com
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
```

**方式 B：桌面端使用配置目录（推荐私有化部署）**

在 Sound Capsule 的配置目录下放置 `.env.supabase`，内容同上：

- **macOS**: `~/Library/Application Support/com.soundcapsule.app/.env.supabase`
- **Windows**: `%APPDATA%\com.soundcapsule.app\.env.supabase`
- **Linux**: `~/.config/com.soundcapsule.app/.env.supabase`

Sidecar 启动 API 时会优先从 **当前传入的 config_dir** 读取该文件；若存在且包含上述两个变量，则使用它们，否则回退到默认云端配置。

---

## 三、在 Supabase SQL Editor 中执行的 SQL（按顺序）

**首次部署**：从 1 到 7 按顺序执行。**已有基础表**：从 2 开始执行到 7；若上传已 403，只需补执行 7。

| 顺序 | 文件路径 | 说明 |
|------|----------|------|
| 1 | `data-pipeline/supabase_schema.sql` | 创建 `cloud_capsules`、`cloud_capsule_tags`、`cloud_capsule_coordinates`、`sync_log_cloud` 及 RLS、触发器、辅助函数等 |
| 2 | `data-pipeline/database/cloud_prisms_schema_fixed.sql` | 创建 `cloud_prisms` 表（棱镜云端同步） |
| 3 | `data-pipeline/database/supabase_migrations/004_cloud_prisms_add_is_active_and_field_data.sql` | 为 `cloud_prisms` 增加 `is_active`、`field_data` 列 |
| 4 | `data-pipeline/database/migrations/001_add_global_read_policies.sql` | （可选）多用户可读 RLS；若报错 `storage.policies` 不存在，可忽略脚本末尾验证查询。**注意**：001 只配置 Storage 的 SELECT，不包含 INSERT。 |
| 5 | `data-pipeline/database/supabase_migrations/005_cloud_capsule_tags_add_keyword_columns.sql` | **必做**。为 `cloud_capsule_tags` 增加 `word_id`、`word_cn`、`word_en`，否则关键词同步失败 |
| 6 | `data-pipeline/database/supabase_migrations/006_cloud_capsule_tags_drop_unique_per_lens.sql` | **必做**。删除 `(user_id, capsule_id, lens_id)` 唯一约束，否则多关键词会 409 Conflict |
| 7 | `data-pipeline/database/supabase_migrations/007_storage_capsule_files_allow_authenticated_upload.sql` | **必做（自建/私有化）**。为 `capsule-files` 添加 INSERT 策略，与云端「Allow authenticated uploads」一致；否则上传会 403、出现「文件上传不完整」 |
| 8 | `data-pipeline/database/supabase_migrations/008_profiles_add_language.sql` | （可选）用户语言偏好 |
| 9 | `data-pipeline/database/supabase_migrations/009_cloud_capsules_embedding_pgvector.sql` | （可选）语义搜索：pgvector 扩展 + `cloud_capsules.embedding` + `semantic_search_capsules` RPC |
| 10 | `data-pipeline/database/supabase_migrations/010_tag_level_embedding.sql` | （可选）标签级语义搜索：`cloud_capsule_tags.embedding` + `semantic_search_capsules_tag_level` RPC |

执行 001 时若报错 `relation "storage.policies" does not exist`，可忽略或注释掉脚本末尾对 `storage.policies` 的查询（自建 Supabase 可能无该视图）。

**009、010** 用于胶囊语义搜索功能；执行 009 后需运行 `backfill_capsule_embeddings.py` 为已有数据填充向量。

---

## 四、Storage：创建 bucket 与策略

在 Supabase Dashboard → **Storage** 中：

1. 新建 bucket，名称：**`capsule-files`**（必须一致）。
2. 设为 **私有**（不勾选 Public）。
3. **读权限**：`001_add_global_read_policies.sql` 会为 `capsule-files` 配置 SELECT（可读）；本地若希望与云端一致，可用「Allow Authenticated Download」仅允许认证用户下载，或保留「Public Read」允许公开读。
4. **写权限（必做）**：自建 Supabase 必须为 `capsule-files` 添加 **INSERT** 策略，否则上传会报 403（`new row violates row-level security policy`），表现为「胶囊 XX 文件上传不完整: 预览音频上传失败, RPP 文件上传失败, …」。001 脚本只包含 SELECT，不包含 INSERT，需在 **SQL Editor** 中单独执行：

```sql
-- 与云端策略一致：允许认证用户上传到 capsule-files
CREATE POLICY "Allow authenticated uploads"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'capsule-files');
```

若习惯用脚本创建 bucket，可配置好 Service Role 后运行：

- `data-pipeline/setup_supabase_storage.py`（会创建 `capsule-files` bucket）。创建后仍需按上一步添加 INSERT 策略。

**胶囊上传失败排查**：若同步时报「胶囊 XX 文件上传不完整: 预览音频上传失败, RPP 文件上传失败, …」，错误详情中会附带 Storage 返回的具体原因。常见情况：

1. **缺少 INSERT 策略（最常见）**：自建 Storage 未为 `capsule-files` 配置 INSERT，导致 403。在 SQL Editor 中执行上方的 `CREATE POLICY "Allow authenticated uploads" ...`。
2. **未创建 bucket**：在自建 Supabase 的 **Storage** 里新建 bucket，名称必须为 `capsule-files`（或在本机执行 `python setup_supabase_storage.py`，需已配置 `.env.supabase`）。
3. **Storage 未启用或端口不同**：自建 Supabase 的 Storage 与 REST 共用同一 `SUPABASE_URL`；若 Storage 单独端口或未启用，需在自建侧确认并统一入口。

---

## 五、Auth（认证）与取消邮件验证

- 项目使用 **Supabase Auth**（邮箱 + 密码）；用户注册/登录后得到 `supabase_user_id`，与本地 `users` 表关联。
- 私有化部署时在自建 Supabase 的 **Authentication** 中启用所需登录方式即可，无需迁移旧业务数据。

### 取消邮件验证（推荐：团队内网 / 手动发账号）

自建 Supabase 若未配置 SMTP，注册会报 **Error sending confirmation email**。建议关闭“注册后发确认邮件”，改为**自动确认**，用户注册后即可用邮箱+密码直接登录；团队账号可由管理员在 Supabase 后台手动添加。

**方式 1：Docker Compose 部署**

在运行 Auth（GoTrue）的服务里增加环境变量并重启。**具体步骤**：

1. **登录部署 Supabase 的那台机器**（例如你的 `192.168.31.71`），用 SSH 或直接在该机操作。
2. **找到 docker-compose 文件**  
   常见路径：`/opt/supabase/docker-compose.yml`、`~/supabase/docker/docker-compose.yml`，或你当时部署时用的目录。可用 `find / -name "docker-compose*.yml" 2>/dev/null | xargs grep -l gotrue 2>/dev/null` 搜含 gotrue 的 compose 文件。
3. **编辑该文件**，找到名为 `auth` 或 `gotrue` 的 service，在它的 `environment:` 里加一行（若已有 `environment:` 就只加这一行；若是列表写法则加 `- GOTRUE_MAILER_AUTOCONFIRM=false`）：

   ```yaml
   # 示例：在 auth 服务里添加（注意：false = 不发邮件、自动确认）
   services:
     auth:                    # 或叫 gotrue
       image: ...
       environment:
         GOTRUE_MAILER_AUTOCONFIRM: "false"   # false = 不发确认邮件，注册后直接可登录
         # 其它已有变量不变...
   ```

4. **重启 Auth 服务**（在放 docker-compose 的目录下执行）：

   ```bash
   docker compose restart auth
   ```

   若服务名是 `gotrue`，则：

   ```bash
   docker compose restart gotrue
   ```

   若用旧版 `docker-compose` 命令：

   ```bash
   docker-compose restart auth
   ```

5. **确认生效**：再在 Sound Capsule 里用邮箱+密码注册，应能直接登录、不再报“Error sending confirmation email”。

**重要**：`GOTRUE_MAILER_AUTOCONFIRM` 含义是「是否要求邮件确认」——设为 **`false`** 才是不发邮件、自动确认；设为 `true` 反而会要求发确认邮件并报错。

**若改 .env 后仍报 “Error sending confirmation email”**：在 docker-compose.yml 里**写死**该变量，不依赖 .env：
- 打开 docker-compose.yml，找到 **auth** 服务里的 `GOTRUE_MAILER_AUTOCONFIRM: ${ENABLE_EMAIL_AUTOCONFIRM}`。
- 改成：`GOTRUE_MAILER_AUTOCONFIRM: "false"`（引号保留）。
- 保存后执行：`docker compose up -d --force-recreate auth`（必须 **--force-recreate** 才会重新读配置）。
- 可选验证：`docker compose exec auth env | grep GOTRUE_MAILER_AUTOCONFIRM`，应看到 `GOTRUE_MAILER_AUTOCONFIRM=false`。

**方式 2：Supabase CLI 本地配置**

在 `supabase/config.toml` 中设置：

```toml
[auth.email]
enable_confirmations = false
```

修改后执行 `supabase stop` 再 `supabase start` 使配置生效。

**手动为团队添加账号**

- 打开自建 Supabase 的 **Dashboard → Authentication → Users**。
- 点击 **Add user → Create new user**，填写邮箱与密码，创建后该用户即可用此邮箱+密码在 Sound Capsule 中登录（无需收邮件）。

---

## 六、执行 SQL 后如何检查测试

1. **配置本地 Supabase 环境**  
   在 `data-pipeline/.env.supabase` 中写好自建实例的 `SUPABASE_URL` 和 `SUPABASE_SERVICE_ROLE_KEY`（不要提交到 Git）。若自建实例为 HTTP，使用 `http://...` 不要用 `https://`。

2. **运行检查脚本（推荐）**  
   - 在**项目根目录**执行：`python data-pipeline/check_private_supabase.py`  
   - 或先进入目录再执行：`cd data-pipeline` → `python check_private_supabase.py`  
   （若当前已在 `data-pipeline` 下，直接运行 `python check_private_supabase.py` 即可。）
   脚本会检查：
   - 连接是否成功（读 `.env.supabase`）
   - 表是否都存在且可查询：`cloud_capsules`、`cloud_capsule_tags`、`cloud_capsule_coordinates`、`sync_log_cloud`、`cloud_prisms`
   - `cloud_prisms` 是否包含 `is_active`、`field_data` 列（004 迁移）
   - Storage 中是否存在名为 `capsule-files` 的 bucket  

   全部通过即说明 SQL（含 005、006）和 Storage 配置正确。

3. **在 Supabase Dashboard 里再确认（可选）**  
   - **Table Editor**：能看到上述 5 张表，点进 `cloud_prisms` 确认有 `is_active`、`field_data` 列；点进 `cloud_capsule_tags` 确认有 `word_id`、`word_cn`、`word_en` 列。  
   - **Storage**：能看到私有 bucket `capsule-files`。

4. **端到端测试（可选）**  
   - 启动应用（桌面端或本地 API），用自建 Supabase 的 Auth 登录（或 Dashboard 手动添加用户后登录）。  
   - 在应用里执行一次「同步到云端」、修改关键词后点「同步」，确认无报错、列表/文件正常。

---

## 七、简要检查清单

- [ ] 自建 Supabase 已部署并可从本机访问（`SUPABASE_URL` 可连通；HTTP 实例用 `http://`）。
- [ ] 在 Supabase SQL Editor 中已按顺序执行：`supabase_schema.sql` → `cloud_prisms_schema_fixed.sql` → `004_...` → 可选 `001_...` → **005** → **006** → **007**（自建必做）；可选 **008**（语言）、**009/010**（语义搜索）。
- [ ] Storage 中已创建私有 bucket `capsule-files`。
- [ ] 在 `data-pipeline/.env.supabase` 或桌面端配置目录下配置了 `SUPABASE_URL` 和 `SUPABASE_SERVICE_ROLE_KEY`。
- [ ] 桌面端：若使用配置目录的 `.env.supabase`，确认路径为 `config_dir/.env.supabase`（即上述 macOS/Windows/Linux 路径）。
- [ ] Auth：已设置 `GOTRUE_MAILER_AUTOCONFIRM: "false"` 或手动在 Dashboard 添加用户；团队账号可只登录不注册。
- [ ] 已运行 `python data-pipeline/check_private_supabase.py` 且全部通过。

完成后，后端与桌面端会使用私有化 Supabase；无需迁移胶囊业务数据，仅需表结构与 bucket 名称一致即可。

---

## 九、搬迁到正式服务器（快速清单）

搬迁到**正式/生产**环境时，按下面顺序做一遍即可。

### 1. 服务器上部署 Supabase

- 在正式机上用 Docker Compose 部署 Supabase（或使用 Supabase 官方自建文档）。
- 记下 **API URL**（如 `http://正式机IP:8000` 或 `https://supabase.你的域名.com`）和 **Service Role Key**（在项目设置 / API 中获取）。

### 2. 执行 SQL（按「三」中顺序）

在 Supabase Studio → **SQL Editor** 中依次执行：

1. `data-pipeline/supabase_schema.sql`
2. `data-pipeline/database/cloud_prisms_schema_fixed.sql`
3. `data-pipeline/database/supabase_migrations/004_cloud_prisms_add_is_active_and_field_data.sql`
4. （可选）`data-pipeline/database/migrations/001_add_global_read_policies.sql`
5. `data-pipeline/database/supabase_migrations/005_cloud_capsule_tags_add_keyword_columns.sql`
6. `data-pipeline/database/supabase_migrations/006_cloud_capsule_tags_drop_unique_per_lens.sql`
7. `data-pipeline/database/supabase_migrations/007_storage_capsule_files_allow_authenticated_upload.sql`
8. （可选）`data-pipeline/database/supabase_migrations/008_profiles_add_language.sql`
9. （可选）`data-pipeline/database/supabase_migrations/009_cloud_capsules_embedding_pgvector.sql`
10. （可选）`data-pipeline/database/supabase_migrations/010_tag_level_embedding.sql`

### 3. Storage 与 Auth

- **Storage**：新建私有 bucket，名称为 **`capsule-files`**。
- **Auth**：在 docker-compose 或 .env 中设置 `GOTRUE_MAILER_AUTOCONFIRM: "false"`（或按「五」写死），重启 auth 服务；或只用 Dashboard → Authentication → Users → Add user 手动添加账号。

### 4. 客户端/本机配置

- 在 **`data-pipeline/.env.supabase`** 中写入正式环境的 `SUPABASE_URL` 和 `SUPABASE_SERVICE_ROLE_KEY`。
- 若用桌面端打包分发，在应用配置目录下放置 `.env.supabase`（见「二」），或确保打包时注入上述两个环境变量。

### 5. 验证

- 运行：`python data-pipeline/check_private_supabase.py`，确认全部通过。
- 打开应用，用正式环境账号登录，做一次「同步到云端」和「修改关键词 → 同步」，确认无报错。

### 6. 注意事项

- 正式环境若用 **HTTPS**，`SUPABASE_URL` 用 `https://...`；若用 **HTTP**（内网），必须用 `http://...`，否则会报 SSL 错误。
- 不迁移旧业务数据时，只需保证表结构与本文档一致；用户在新 Supabase 上重新注册或由管理员手动添加即可。
- **锚点编辑器**：与主应用共用 `data-pipeline/.env.supabase`，换新服务器后只需改该文件，锚点编辑器的「同步到云端」即指向新 Supabase。若新服务器上**棱镜管理员**用的是新账号（不同 UUID），需在 `data-pipeline/dal_cloud_prisms.py` 中把 `CloudPrismDAL.ADMIN_USER_ID` 改成新服务器上该管理员的 `supabase_user_id`（在 Supabase Dashboard → Authentication → Users 中可查），否则棱镜上传会被判定为非管理员而跳过。

---

## 八、常见问题

### 注册失败: Error sending confirmation email

**原因**：自建 Supabase 未配置发信（SMTP），注册时会尝试发确认邮件并失败。

**处理**：关闭邮件确认，改为自动确认（见 **五、Auth（认证）与取消邮件验证**）：  
- Docker：在 .env 里设 `ENABLE_EMAIL_AUTOCONFIRM=false`（或给 Auth 服务加 `GOTRUE_MAILER_AUTOCONFIRM: "false"`）后重启。  
- CLI：在 `supabase/config.toml` 里设 `[auth.email] enable_confirmations = false` 后 `supabase stop` 再 `supabase start`。

团队账号可在 **Dashboard → Authentication → Users → Add user** 里手动创建，用户用邮箱+密码即可登录，无需收邮件。

---

### SSL: WRONG_VERSION_NUMBER / wrong version number

**原因**：自建 Supabase 在局域网用 **HTTP**（无 TLS）提供服务，但 `.env.supabase` 里写的是 `https://...`，客户端按 HTTPS 做 TLS 握手，服务端返回的是明文 HTTP，就会报错。

**处理**：把 `SUPABASE_URL` 改成 **http**（不要用 https），例如：

```env
SUPABASE_URL=http://192.168.31.71:8000
```

保存后重新运行 `python check_private_supabase.py`。若自建实例确实启用了 HTTPS 并配置了证书，则保持 `https://` 并检查证书与端口是否正确。
