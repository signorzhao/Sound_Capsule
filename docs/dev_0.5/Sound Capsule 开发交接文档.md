

**生成时间**: 2026-01-13

**项目状态**: Phase G2 开发中（启动同步功能）

**代码库位置**: `/Users/ianzhao/Desktop/Sound_Capsule/synesth`

  

---

  

## 📊 项目概述

  

### 项目简介

**Sound Capsule**（代号 Synesth）是一个基于 AI 语义向量技术的声音形容词探索工具，专为声音设计师和游戏音频专家打造。系统将抽象的感性描述转化为直观的几何空间，通过多点引力加权算法实现声音关键词的精准导航。

  

### 技术栈

**前端**:

- React 18.2.0 + TypeScript

- Vite 5.0.0 构建工具

- TailwindCSS 3.4.19

- Tauri 2.9.6 跨平台桌面应用

  

**后端**:

- Python 3.x + Flask 2.3.0

- SQLite 本地数据库

- Supabase 云服务（数据库、认证、存储）

- PyJWT 2.8.0 认证体系

  

**核心算法**:

- sentence-transformers 语义向量模型

- scikit-learn 数据处理

- 余弦相似度指数加权算法

  

---

  

## 🔄 最近 Git 提交历史

  

### 关键里程碑（按时间倒序）

  

| 提交哈希 | 功能描述 | 开发阶段 |

|---------|---------|---------|

| `b02feb6` | JIT 决策流下载功能 + 跨用户下载修复 | Phase G |

| `4861e26` | 云同步功能和服务管理面板优化 | Phase G |

| `c291967` | **完整的云端同步功能 - Phase B 完成** | Phase B ✅ |

| `5dfaae2` | SoundMap v2.0 - 语义架构重构 | Phase G 准备 |

  

**当前分支**: `main`（与 origin/main 同步）

  

---

  

## ⚠️ 当前问题状态

  

### 🔴 紧急问题：BootSync 完全卡住

  

**问题描述**: 启动同步界面完全冻结，无法进入 App

  

**根本原因**: [BootSync.jsx:200](webapp/src/components/BootSync.jsx#L200) 引用了已删除的 `syncStatus` 变量

  

```jsx

// ❌ 错误代码（第200行）

{syncStatus.syncError || '同步过程中发生错误'}

```

  

**修复方案**:

```jsx

// ✅ 正确代码

{error || '同步过程中发生错误'}

```

  

**影响范围**:

- 用户无法进入应用

- 必须手动点击"跳过"才能使用

- 用户体验严重受损

  

**修复位置**: `/Users/ianzhao/Desktop/Sound_Capsule/synesth/webapp/src/components/BootSync.jsx:200`

  

---

  

### 🟡 次要问题：元数据提取逻辑已修复

  

**修复内容**:

- ✅ `sync_service.py` 的 `_update_local_capsule_metadata()` 已修复

- ✅ `_create_local_capsule_from_cloud()` 已修复

- ✅ 现在能正确从云端 `metadata` JSON 字段提取 `keywords`、`description`、`capsule_type`

  

**验证数据**:

```

数据库检查结果（修复前）:

- capsule_type: template ✅

- keywords: 低频感, 镶边, 激励器 ✅

- description: 空（正常，云端数据本身为空）

```

  

---

  

## 📋 当前未提交更改

  

### 已删除文件（12个）

- GitHub Actions: `.github/workflows/build-windows-*.yml`

- 构建脚本: `build_portable_windows.*`

- 文档: `BUILD_PORTABLE_README.md`, `JIT_*_REPORT.md` 等

  

### 已修改文件（17个）

**后端核心**:

- `data-pipeline/sync_service.py` - 元数据提取逻辑修复

- `data-pipeline/capsule_api.py` - API 路由更新

- `data-pipeline/auth.py` - 认证逻辑

- `data-pipeline/capsule_db.py` - 数据库操作

  

**前端核心**:

- `webapp/src/components/BootSync.jsx` - ⚠️ 有 BUG（卡住问题）

- `webapp/src/components/SyncIndicator.jsx` - 同步指示器

- `webapp/src/contexts/SyncContext.jsx` - 同步状态管理

- `webapp/src/utils/apiClient.js` - API 客户端

- `webapp/src/App.jsx` - 应用入口

  

**数据库**:

- `data-pipeline/database/capsules.db` - 有数据

  

### 未跟踪文件（18个）

- **新增功能**: `data-pipeline/routes/` 目录

- **新增组件**: `webapp/src/components/BootSync.jsx`

- **新增文档**: `docs/Globalsync/` 目录

- **数据库备份**: 多个 `.backup` 文件

  

---

  

## 🎯 Phase G（全球化架构）开发进度

  

### ✅ 已完成功能（60%）

  

#### 1. 数据库支持 ✅

- `owner_supabase_user_id` 字段已添加

- 索引 `idx_capsules_owner_id` 已创建

- Schema 支持多用户数据共存

  

#### 2. 同步服务核心 ✅

**文件**: `data-pipeline/sync_service.py`

  

```python

# 已实现的关键方法：

- download_only() # 启动同步专用（仅下载）

- sync_metadata_lightweight() # 轻量资产同步

- _create_local_capsule_from_cloud() # 从云端创建本地胶囊

- _update_local_capsule_metadata() # 更新本地元数据

```

  

**功能特性**:

- ✅ 全球胶囊元数据下载（所有用户）

- ✅ 正确处理 owner_supabase_user_id

- ✅ 从 metadata JSON 提取完整字段

- ✅ JIT 下载策略（按需下载 WAV）

- ✅ 增量同步（基于时间戳）

  

#### 3. JIT 下载功能 ✅

**文件**: `data-pipeline/capsule_download_api.py`

  

- ✅ 跨用户下载支持

- ✅ 后台线程下载

- ✅ 完整的状态跟踪

- ✅ 断点续传

  

#### 4. 前端 JIT 组件 ✅

- ✅ `SmartActionButton.jsx` - 智能按钮（根据状态显示不同操作）

- ✅ `DownloadConfirmModal.jsx` - 下载决策弹窗

- ✅ `CapsuleLibrary.jsx` - 集成 JIT 逻辑

  

#### 5. Supabase 客户端 ✅

**文件**: `data-pipeline/supabase_client.py`

  

- ✅ `download_capsules()` - 获取所有用户胶囊

- ✅ `get_capsule_count()` - 统计所有用户胶囊

  

#### 6. RLS 策略文档 ✅

**文件**: `data-pipeline/database/migrations/001_add_global_read_policies.sql`

  

- ✅ 完整的 RLS 策略配置方案

- ✅ 回滚脚本

- ✅ 测试查询示例

  

---

  

### ⏳ 未完成功能（40%）

  

#### 1. 前端 UI 适配 ⏳

**相关文件**: `CapsuleLibrary.jsx`, `CapsuleCard.jsx`

  

- [ ] 显示作者信息（Avatar + Name）

- [ ] 实现 `is_mine = (current_user_id == capsule_owner_id)` 逻辑

- [ ] 如果 `!is_mine`，隐藏"删除"和"编辑"按钮

- [ ] 添加筛选器：`[全部] [我的] [已下载]`

  

#### 2. Supabase RLS 策略部署 ⏳

- [ ] 在 Supabase SQL Editor 执行 RLS 配置

- [ ] 验证所有用户可以读取胶囊

- [ ] 验证只有所有者可以修改

  

#### 3. 用户状态管理 ⏳

- [ ] 集成 Supabase Auth 到前端

- [ ] 获取当前登录用户信息

- [ ] 实现用户登录状态持久化

  

#### 4. 胶囊 API 增强 ⏳

**文件**: `capsule_api.py`

  

- [ ] 修改 `/api/capsules` 返回 `owner_info`

- [ ] 实现权限验证装饰器 `@check_ownership`

- [ ] 对非所有者胶囊返回 403 Forbidden

  

  

---

  

## 🗂️ 关键文件索引

  

### 后端文件

| 文件路径 | 功能描述 | 状态 |

|---------|---------|------|

| `data-pipeline/sync_service.py` | 同步服务核心 | ✅ 完成 |

| `data-pipeline/capsule_download_api.py` | JIT 下载 API | ✅ 完成 |

| `data-pipeline/supabase_client.py` | Supabase 客户端 | ✅ 完成 |

| `data-pipeline/capsule_api.py` | 胶囊 API | ⏳ 需增强 |

| `data-pipeline/capsule_db.py` | 数据库操作 | ✅ 完成 |

| `data-pipeline/auth.py` | 认证服务 | ✅ 完成 |

  

### 前端文件

| 文件路径 | 功能描述 | 状态 |

|---------|---------|------|

| `webapp/src/components/BootSync.jsx` | 启动同步组件 | ⚠️ **有BUG** |

| `webapp/src/contexts/SyncContext.jsx` | 同步状态管理 | ✅ 完成 |

| `webapp/src/components/SyncIndicator.jsx` | 同步指示器 | ✅ 完成 |

| `webapp/src/components/CapsuleLibrary.jsx` | 胶囊库主组件 | ⏳ 需适配 |

| `webapp/src/components/SmartActionButton.jsx` | JIT 智能按钮 | ✅ 完成 |

| `webapp/src/components/DownloadConfirmModal.jsx` | 下载决策弹窗 | ✅ 完成 |

| `webapp/src/utils/apiClient.js` | API 客户端 | ✅ 完成 |

  

### 数据库文件

| 文件路径 | 说明 |

|---------|------|

| `data-pipeline/database/capsules.db` | 主数据库（有数据） |

| `data-pipeline/database/capsule_schema.sql` | Schema 定义 |

| `data-pipeline/database/migrations/001_add_global_read_policies.sql` | RLS 策略（未部署）|

  

### 文档文件

| 文件路径 | 说明 |

|---------|------|

| `docs/Globalsync/` | Phase G 开发文档目录 |

| `docs/Globalsync/Todo List (执行清单).md` | 任务清单 |

| `docs/Globalsync/Sound Capsule 协作架构开发指南 v1.0.md` | 架构设计 |

  

---

  

## 🔧 立即需要修复的问题

  

### 1. BootSync 组件卡住（紧急）

  

**问题**: [BootSync.jsx:200](webapp/src/components/BootSync.jsx#L200)

  

```jsx

// ❌ 当前代码

{syncStatus.syncError || '同步过程中发生错误'}

```

  

**修复**:

```jsx

// ✅ 应该改为

{error || '同步过程中发生错误'}

```

  

**原因**:

- 已移除 `useSync()` 中的 `syncStatus` 依赖

- 但第200行仍在引用 `syncStatus.syncError`

- 导致组件报错并卡住

  

**测试**:

1. 修复后重新启动应用

2. 验证同步完成后自动进入 App

3. 验证错误信息正确显示

  

---

  

## 📝 开发交接要点

  

### 核心概念理解

  

#### 1. Phase G 架构目标

将 Sound Capsule 从"单机版"升级为"全球共享版":

- ✅ 任何用户可以上传自己的胶囊

- ✅ 任何用户都能看到、搜索并下载其他用户的胶囊

- ✅ 只有作者拥有修改和删除自己胶囊的权限

- ✅ 本地优先：所有数据优先存储在本地 SQLite

  

#### 2. 启动同步（BootSync）设计理念

- **仅下载模式**: 启动时不上传本地数据，避免每次启动都上传

- **轻量资产**: 只下载元数据 + OGG 预览 + RPP 文件

- **按需下载**: WAV 源文件采用 JIT 策略，用户点击"导入"时才下载

- **用户体验**: 30秒后允许跳过，避免强制等待

  

#### 3. 元数据提取逻辑（重要！）

```python

# 云端存储结构

cloud_capsules 表:

- id, name, description (可能为空)

- user_id (所有者)

- metadata (JSON 字段，包含完整数据)

  

# 本地提取逻辑

metadata = cloud_data.get('metadata', {})

if isinstance(metadata, dict):

keywords = metadata.get('keywords') # ✅ 从 metadata 提取

description = metadata.get('description') # ✅ 从 metadata 提取

capsule_type = metadata.get('capsule_type') # ✅ 从 metadata 提取

preview_audio = metadata.get('preview_audio') # ✅ 从 metadata 提取

else:

# Fallback 到顶层字段（兼容旧数据）

keywords = cloud_data.get('keywords')

```

  

**关键点**:

- 上传时，`capsule_api.py` 将整个 `capsule_data` 对象存储到 `metadata` 字段

- 下载时，必须从 `metadata` 中提取完整字段

- 不能直接从 `cloud_data` 顶层获取（字段可能为空）

  

#### 4. 文件下载路径配置

**关键配置**:

```json

// 用户配置文件

/Users/ianzhao/Library/Application Support/com.soundcapsule.app/config.json

{

"export_dir": "/Users/ianzhao/Documents/t111" // 用户导出目录

}

```

  

**读取方式**:

```python

from capsule_api import load_user_config

user_config = load_user_config()

export_dir = Path(user_config.get('export_dir', 'output'))

```

  

**错误示例** (已修复):

```python

# ❌ 错误：使用服务器的 EXPORT_DIR

from common import EXPORT_DIR

export_dir = EXPORT_DIR # 解析为相对路径 'output'

```

  

---

  

## 🚀 下一步行动建议

  

### 立即执行（今天）

1. **修复 BootSync 卡住问题** (10分钟)

- 修改 [BootSync.jsx:200](webapp/src/components/BootSync.jsx#L200)

- 测试启动同步流程

- 验证自动进入 App

  

2. **提交当前更改** (5分钟)

- 创建 Git commit

- 推送到远程仓库

- 确保代码安全

  

### 本周完成

3. **部署 Supabase RLS 策略** (30分钟)

- 在 Supabase SQL Editor 执行 `001_add_global_read_policies.sql`

- 验证多用户读取权限

- 测试权限隔离

  

4. **前端用户状态管理** (2小时)

- 集成 Supabase Auth

- 实现 `is_mine` 逻辑

- 添加作者信息显示

  

### 下周完善

5. **胶囊 API 增强和 UI 适配** (4小时)

- 添加 `owner_info` 返回

- 实现权限验证

- 添加筛选器功能

  

---

  

## 📞 联系信息

  

**开发者交接对象**: 新接手项目的开发团队

  

**关键联系人**:

- 项目架构师: （待填写）

- 前端负责人: （待填写）

- 后端负责人: （待填写）

  

**重要提醒**:

1. ⚠️ **立即修复 BootSync 卡住问题**，否则用户无法使用

2. ⚠️ **不要直接修改云端数据**，RLS 策略尚未部署

3. ⚠️ **测试时使用测试账号**，避免污染生产数据

  

---

  

## 附录：快速诊断命令

  

### 检查数据库状态

```bash

sqlite3 data-pipeline/database/capsules.db "SELECT COUNT(*) FROM capsules;"

sqlite3 data-pipeline/database/capsules.db "SELECT COUNT(DISTINCT owner_supabase_user_id) FROM capsules;"

```

  

### 检查同步服务

```bash

cd data-pipeline

python -c "from sync_service import get_sync_service; print('Sync service OK')"

```

  

### 检查前端构建

```bash

cd webapp

npm run build

npm run tauri build

```

  

---

  

**文档版本**: v2.0

**最后更新**: 2026-01-13

**状态**: 🔴 紧急修复 BootSync 卡住问题