# 私有化 Supabase 快速复用部署指南

在**已完成首次私有化部署**的前提下，将现有成果复制到新服务器，实现快速部署。无需重新执行 SQL、配置密钥或创建 bucket。

---

## 目录

1. [适用场景](#一适用场景)
2. [可复用的内容](#二可复用的内容)
3. [方式 A：完整迁移（含数据）](#三方式-a完整迁移含数据)
4. [方式 B：仅配置迁移（不含业务数据）](#四方式-b仅配置迁移不含业务数据)
5. [客户端配置更新](#五客户端配置更新)
6. [验证清单](#六验证清单)

---

## 一、适用场景

- 换新服务器，希望原样迁移 Supabase（含数据库、Storage、用户等）
- 部署到多台环境（开发/测试/生产），希望快速复用已配置好的项目
- 备份后快速恢复

---

## 二、可复用的内容

| 内容 | 路径 | 说明 |
|------|------|------|
| 项目配置 | `supabase-project/` | docker-compose、.env（密钥）、volumes 配置 |
| 密钥与凭证 | `supabase-project/.env` | JWT、数据库密码、Kong 账号等，**复用则客户端无需改 Key** |
| 数据库数据 | `supabase-project/volumes/db/data/` | PostgreSQL 数据目录，含表、数据、RLS 等 |
| Storage 文件 | `supabase-project/volumes/storage/` | 上传的文件（如 capsule-files 内容） |
| SQL 脚本（备份参考） | `database/` | 建表 SQL，完整迁移时可不执行 |

---

## 三、方式 A：完整迁移（含数据）

适用于：换服务器、灾备恢复，需要**保留所有数据和配置**。

### 3.1 在源服务器上打包

**方式一：使用备份脚本（推荐）**

```bash
cd /home/sbadmin
chmod +x backup-supabase.sh
./backup-supabase.sh
```

脚本会执行 `docker compose down` 并打包，生成 `supabase-full-YYYYMMDD-HHMM.tar.gz`。

**方式二：手动执行**

```bash
cd /home/sbadmin/supabase-project
docker compose down
cd ..
tar -czvf supabase-backup-$(date +%Y%m%d).tar.gz supabase-project/ database/
```

生成文件示例：`supabase-backup-20250131.tar.gz` 或 `supabase-full-20250131-1200.tar.gz`

### 3.2 传输到新服务器

```bash
# 示例：scp 传输
scp supabase-backup-20250131.tar.gz user@新服务器IP:/home/sbadmin/

# 或 rsync
rsync -avz supabase-backup-20250131.tar.gz user@新服务器IP:/home/sbadmin/
```

### 3.3 在新服务器上解包并启动

**方式一：使用恢复脚本（推荐）**

```bash
# 1. 安装 Docker（若未安装）
sudo apt-get update
sudo apt-get install -y docker.io
sudo usermod -aG docker $USER
newgrp docker

# 2. 将备份脚本和备份文件传到新服务器后
chmod +x restore-supabase.sh
./restore-supabase.sh /home/sbadmin/supabase-full-20250131-1200.tar.gz
```

**方式二：手动解包**

```bash
cd /home/sbadmin
tar -xzvf supabase-backup-20250131.tar.gz  # 或 supabase-full-xxx.tar.gz
cd supabase-project
docker compose pull
docker compose up -d
docker compose ps
```

### 3.4 完成后

- **无需**再执行 SQL
- **无需**再创建 Storage bucket
- **无需**更换 Service Role Key（若 .env 一致）
- **只需**更新客户端的 `SUPABASE_URL` 为新服务器 IP（见 [第五节](#五客户端配置更新)）

---

## 四、方式 B：仅配置迁移（不含业务数据）

适用于：在新环境部署**全新实例**，表结构、密钥、Storage 配置复用，但不带旧数据。

### 4.1 在源服务器上打包（排除数据）

```bash
cd /home/sbadmin

# 只打包配置和 SQL，不打包数据库数据与 Storage 文件
tar -czvf supabase-config-only-$(date +%Y%m%d).tar.gz \
  supabase-project/.env \
  supabase-project/docker-compose.yml \
  supabase-project/docker-compose.s3.yml \
  supabase-project/volumes/ \
  database/

# 注意：会排除 volumes/db/data（若存在且为空则无影响）
# 若 volumes 中含 data，需手动排除：
tar -czvf supabase-config-only-$(date +%Y%m%d).tar.gz \
  --exclude='supabase-project/volumes/db/data' \
  supabase-project/ \
  database/
```

### 4.2 在新服务器上解包并初始化

```bash
# 1. 安装 Docker（同方式 A）

# 2. 解包
cd /home/sbadmin
tar -xzvf supabase-config-only-20250131.tar.gz

# 3. 创建数据库数据目录（首次启动需要）
mkdir -p supabase-project/volumes/db/data

# 4. 启动（会初始化空数据库）
cd supabase-project
docker compose pull
docker compose up -d

# 5. 等待服务就绪
sleep 30
docker compose ps
```

### 4.3 执行 SQL（必须）

因为未迁移数据库数据，需重新建表。按 **完整部署指南** 第五节顺序执行 1～7：

1. 浏览器打开 `http://<新服务器IP>:8000`，登录 Kong
2. 进入 **SQL Editor**
3. 按顺序执行 `database/` 下 **001～007**：`001_supabase_schema.sql` → `002_cloud_prisms_schema_fixed.sql` → … → **`007_storage_capsule_files_allow_authenticated_upload.sql`**。**007 为自建必做**，否则上传 403。

### 4.4 创建 Storage Bucket 与上传策略

在 Studio → Storage → New bucket，名称 `capsule-files`，私有。**并执行 007**（或手动为 `capsule-files` 添加 INSERT 策略），否则上传会 403。

### 4.5 完成后

- 表结构、密钥与源一致
- 数据库为空，Storage 为空
- 客户端 `SUPABASE_URL` 改为新服务器 IP，`SUPABASE_SERVICE_ROLE_KEY` 可保持不变

---

## 五、客户端配置更新

迁移后，只需将客户端指向**新服务器 IP**。

### 5.1 data-pipeline

编辑 `data-pipeline/.env.supabase`：

```env
SUPABASE_URL=http://<新服务器IP>:8000
SUPABASE_SERVICE_ROLE_KEY=<保持不变，若 .env 未改>
```

### 5.2 桌面端配置目录

更新 `~/Library/Application Support/com.soundcapsule.app/.env.supabase`（macOS）等路径下的 `SUPABASE_URL`。

### 5.3 验证连接

```bash
curl -s "http://<新服务器IP>:8000/rest/v1/" \
  -H "apikey: <SERVICE_ROLE_KEY>" \
  -H "Authorization: Bearer <SERVICE_ROLE_KEY>"
```

返回 OpenAPI JSON 即表示连接正常。

---

## 六、验证清单

- [ ] `docker compose ps` 所有服务为 running
- [ ] 可访问 `http://<新服务器IP>:8000` 并登录
- [ ] （方式 A）Table Editor 中可见原有表和数据
- [ ] （方式 B）已执行 SQL 1～7（含 007），表结构正确
- [ ] Storage 中有 `capsule-files` bucket，且已执行 007（INSERT 策略）
- [ ] 客户端 `SUPABASE_URL` 已更新为新 IP
- [ ] `curl` 或应用测试连接正常

---

## 附录：备份与恢复脚本

### 备份脚本 `backup-supabase.sh`

位置：`/home/sbadmin/backup-supabase.sh`

- 执行 `docker compose down` 停止并移除容器
- 打包 `supabase-project/` 与 `database/`
- **不会自动启动**，需手动执行 `docker compose up -d` 启动

```bash
chmod +x /home/sbadmin/backup-supabase.sh
./backup-supabase.sh
```

### 恢复脚本 `restore-supabase.sh`

位置：`/home/sbadmin/restore-supabase.sh`

- 用法：`./restore-supabase.sh <备份文件路径>`
- 解包 → 拉取镜像 → 启动服务

```bash
chmod +x /home/sbadmin/restore-supabase.sh
./restore-supabase.sh /home/sbadmin/supabase-full-20250131-1200.tar.gz
```

---

*文档版本：2025-01 | 配合《Sound_Capsule_私有化Supabase_完整部署指南.md》使用*
