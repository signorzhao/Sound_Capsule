# Sound Capsule 私有化 Supabase 完整部署指南

从系统安装到搭建测试完成的**一站式部署文档**。

---

## 目录

1. [环境准备](#一环境准备)
2. [安装 Docker](#二安装-docker)
3. [配置 Docker 镜像加速（可选，推荐国内环境）](#三配置-docker-镜像加速可选推荐国内环境)
4. [部署 Supabase](#四部署-supabase)
5. [执行 SQL 建表](#五执行-sql-建表)
6. [创建 Storage Bucket](#六创建-storage-bucket)
7. [配置客户端连接](#七配置客户端连接)
8. [验证与测试](#八验证与测试)
9. [故障排查](#九故障排查)

---

## 一、环境准备

### 1.1 服务器要求

- **操作系统**：Ubuntu 20.04+ 或 Debian 11+（其他 Linux 发行版需自行适配）
- **内存**：建议 4GB 以上
- **磁盘**：建议 20GB 可用空间
- **网络**：可访问互联网（拉取 Docker 镜像）

### 1.2 客户端要求（本机 Mac/Windows/Linux）

- 与服务器在同一局域网，或通过端口转发可访问服务器
- 用于运行 Sound Capsule 及 data-pipeline

---

## 二、安装 Docker

在 **Linux 服务器**上执行：

```bash
# 更新软件源
sudo apt-get update

# 安装 Docker
sudo apt-get install -y docker.io

# 将当前用户加入 docker 组
sudo usermod -aG docker $USER

# 使组权限生效（二选一）
# 方式 A：注销后重新登录
# 方式 B：执行
newgrp docker
```

验证安装：

```bash
docker --version
```

---

## 三、配置 Docker 镜像加速（可选，推荐国内环境）

若 `docker compose pull` 出现 `context deadline exceeded` 或拉取超时，可配置国内镜像源：

```bash
# 创建配置目录
sudo mkdir -p /etc/docker

# 写入镜像加速配置
sudo tee /etc/docker/daemon.json > /dev/null << 'EOF'
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ]
}
EOF

# 重启 Docker
sudo systemctl restart docker
```

---

## 四、部署 Supabase

### 4.1 准备部署脚本

确保服务器上有 `deploy-supabase.sh`（通常位于 `/home/sbadmin/`）：

```bash
cd /home/sbadmin
chmod +x deploy-supabase.sh
```

### 4.2 执行部署

```bash
./deploy-supabase.sh
```

脚本将依次完成：

1. 克隆 Supabase 仓库
2. 复制 Docker 配置到 `supabase-project/`
3. 生成 JWT 密钥等（写入 `.env`）
4. 拉取 Docker 镜像
5. 启动所有服务

若 `generate-keys.sh` 报错，可手动编辑 `supabase-project/.env`，设置 `POSTGRES_PASSWORD`、`JWT_SECRET` 等后重试。

### 4.3 启动后检查

```bash
cd /home/sbadmin/supabase-project
docker compose ps
```

所有服务应为 `running` 状态。

### 4.4 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| **Supabase Studio（管理界面）** | `http://<服务器IP>:8000` | 通过 Kong 网关访问 |
| **API / REST** | `http://<服务器IP>:8000` | 同上 |
| **PostgreSQL 直连** | `<服务器IP>:5432` | 仅供数据库工具，非 Web 访问 |

**登录 Studio**：浏览器访问 `http://<服务器IP>:8000` 时，会提示输入 Kong 凭证：
- 用户名：`supabase`（或 `.env` 中 `DASHBOARD_USERNAME`）
- 密码：`.env` 中 `DASHBOARD_PASSWORD` 的值

---

## 五、执行 SQL 建表

### 5.1 打开 SQL Editor

1. 浏览器访问 `http://<服务器IP>:8000`
2. 输入 Kong 用户名、密码登录
3. 进入 **SQL Editor**

### 5.2 执行顺序

**注意**：不要直接输入 `cat` 等终端命令，应复制 **SQL 文件内容** 到 SQL Editor 执行。**007 为自建必做**，否则上传会 403（「文件上传不完整」）。

| 顺序 | 文件名（均在 `database/` 下） | 说明 |
|------|------------------------------|------|
| 1 | `001_supabase_schema.sql` | 胶囊表 + sync_log + RLS |
| 2 | `002_cloud_prisms_schema_fixed.sql` | 创建 cloud_prisms |
| 3 | `003_cloud_prisms_add_is_active_field_data.sql` | 添加 is_active、field_data |
| 4（可选） | `004_add_global_read_policies.sql` | 全局读策略；**仅含 Storage SELECT，不含 INSERT** |
| 5 | `005_cloud_capsule_tags_add_keyword_columns.sql` | **必做**。关键词列，否则关键词同步失败 |
| 6 | `006_cloud_capsule_tags_drop_unique_per_lens.sql` | **必做**。删除唯一约束，否则多关键词 409 |
| 7 | **`007_storage_capsule_files_allow_authenticated_upload.sql`** | **必做（自建）**。为 capsule-files 添加上传策略；否则上传 403 |

### 5.3 操作方法

在服务器上 `database/` 即 `/home/sbadmin/database/`（或本机项目 `docs/deployment-docs/database/`）。用 `cat` 查看文件内容，复制输出到 SQL Editor 执行；或在本机用编辑器打开对应文件，复制内容后执行。

---

## 六、创建 Storage Bucket 与上传策略

### 6.1 创建 bucket

**方式 A：Dashboard（推荐）**

1. 在 Supabase Studio 中打开 **Storage**
2. 点击 **New bucket**
3. 名称填：`capsule-files`
4. **不勾选** Public（保持私有）
5. 确认创建

**方式 B：SQL**

在 SQL Editor 中执行：

```sql
INSERT INTO storage.buckets (id, name, public)
VALUES ('capsule-files', 'capsule-files', false)
ON CONFLICT (id) DO NOTHING;
```

### 6.2 添加上传策略（必做）

001 只配置了 **SELECT**（读），未配置 **INSERT**（写）。自建必须为 `capsule-files` 添加 **INSERT** 策略，否则上传会 403（`new row violates row-level security policy`），表现为「胶囊 XX 文件上传不完整」。

在 SQL Editor 中执行 **`database/007_storage_capsule_files_allow_authenticated_upload.sql`**（本目录已包含，与云端「Allow authenticated uploads」一致）。

---

## 七、配置客户端连接

### 7.1 获取 Service Role Key

在**服务器**上执行：

```bash
grep SERVICE_ROLE_KEY /home/sbadmin/supabase-project/.env
```

复制输出的长串 JWT（形如 `eyJhbGciOiJIUzI1NiIs...`）。

### 7.2 配置 data-pipeline（开发时）

在 Sound Capsule 项目的 `data-pipeline/.env.supabase` 中填写：

```env
SUPABASE_URL=http://<服务器IP>:8000
SUPABASE_SERVICE_ROLE_KEY=<上一步获取的 JWT>
```

**注意**：`SUPABASE_URL` 必须包含 `http://` 前缀。

### 7.3 配置桌面端（私有化部署推荐）

在 Sound Capsule 的配置目录下创建 `.env.supabase`：

| 系统 | 路径 |
|------|------|
| **macOS** | `~/Library/Application Support/com.soundcapsule.app/.env.supabase` |
| **Windows** | `%APPDATA%\com.soundcapsule.app\.env.supabase` |
| **Linux** | `~/.config/com.soundcapsule.app/.env.supabase` |

内容同上。Sidecar 启动时会优先读取该文件。

**安全**：不要将 `.env.supabase` 提交到 Git，确保在 `.gitignore` 中。

---

## 八、验证与测试

### 8.1 验证 SQL 执行结果

在 Supabase Studio → SQL Editor 中执行 `verify_schema.sql`：

```bash
# 在服务器上查看内容
cat /home/sbadmin/database/verify_schema.sql
```

复制输出到 SQL Editor 执行。预期结果：

- **表**：5 张表均存在（cloud_capsules、cloud_capsule_tags、cloud_capsule_coordinates、sync_log_cloud、cloud_prisms）
- **cloud_prisms**：含 `is_active`、`field_data` 列
- **RLS**：每张表有至少 1 条策略
- **Storage**：`capsule-files` bucket 存在，`public = false`

### 8.2 测试 API 连接

在本机（Mac/Windows）终端执行（将 `<服务器IP>` 和 `<SERVICE_ROLE_KEY>` 替换为实际值）：

```bash
curl -s "http://<服务器IP>:8000/rest/v1/" \
  -H "apikey: <SERVICE_ROLE_KEY>" \
  -H "Authorization: Bearer <SERVICE_ROLE_KEY>"
```

**成功**：返回一大段 OpenAPI/JSON，包含 `cloud_capsules`、`cloud_prisms` 等表定义。

**失败**：返回 `{"message":"Invalid authentication credentials"}`，检查 Key 是否正确、是否有 `http://` 前缀。

### 8.3 启动应用测试

1. 启动 Sound Capsule 桌面端
2. 或运行 data-pipeline 相关服务
3. 在 Supabase Studio 的 Table Editor 或 Storage 中查看是否有数据写入

---

## 九、故障排查

### 9.1 Docker 拉取超时

- **现象**：`context deadline exceeded`，每次报错的镜像名可能不同
- **原因**：访问 Docker Hub 超时（国内常见）
- **解决**：按 [第三节](#三配置-docker-镜像加速可选推荐国内环境) 配置镜像加速后重试 `docker compose pull`

### 9.2 无法访问 http://服务器IP:8000

- 检查 `docker compose ps` 是否全部 running
- 检查服务器防火墙是否放行 8000 端口
- 检查本机与服务器是否在同一网段

### 9.3 Kong 登录失败

- 用户名/密码来自 `supabase-project/.env` 中的 `DASHBOARD_USERNAME`、`DASHBOARD_PASSWORD`

### 9.4 SQL Editor 报错「syntax error at or near "cat"」

- `cat` 是终端命令，不是 SQL。应先在终端执行 `cat` 查看文件内容，再将**输出内容**复制到 SQL Editor 执行。

### 9.5 连接测试返回 Invalid authentication credentials

- 检查是否用了实际 Key，而非占位符 `<你的_SERVICE_ROLE_KEY>`
- 检查 `SUPABASE_URL` 是否包含 `http://`

### 9.6 上传报 403 或「文件上传不完整」

- **原因**：自建 Storage 未为 `capsule-files` 配置 **INSERT** 策略（001 只含 SELECT）。
- **解决**：在 SQL Editor 中执行 **`database/007_storage_capsule_files_allow_authenticated_upload.sql`**。

---

## 附录：文件位置速查

| 类型 | 路径 |
|------|------|
| 部署脚本 | `/home/sbadmin/deploy-supabase.sh` |
| Supabase 项目 | `/home/sbadmin/supabase-project/` |
| 环境变量 | `/home/sbadmin/supabase-project/.env` |
| SQL 目录 | `/home/sbadmin/database/` |
| 验证脚本 | `/home/sbadmin/database/verify_schema.sql` |
| 执行顺序说明 | `/home/sbadmin/database/执行顺序.md` |

---

## 检查清单（完成一项勾选一项）

- [ ] Docker 已安装并可用
- [ ] （可选）Docker 镜像加速已配置
- [ ] `deploy-supabase.sh` 执行成功，所有容器 running
- [ ] 可访问 `http://<服务器IP>:8000` 并登录 Kong
- [ ] 已按顺序执行 SQL：1～7（其中 **005、006、007 必做**；007 为 Storage 上传策略）
- [ ] Storage 已创建私有 bucket `capsule-files`，并已执行 **007**（或手动添加 INSERT 策略）
- [ ] 本机已配置 `.env.supabase`（data-pipeline 或桌面端配置目录）
- [ ] `curl` 连接测试返回 OpenAPI JSON
- [ ] Sound Capsule 或 data-pipeline 能正常连接并上传

---

*文档版本：2025-01 | 适用于 Sound Capsule 私有化 Supabase 部署*
