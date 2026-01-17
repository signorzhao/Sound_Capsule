# Phase C: Supabase 云端集成计划

**日期**: 2026-01-10
**状态**: 规划中

---

## 📋 概述

将 Phase B 的本地同步框架升级为真实的云端同步，使用 Supabase 作为后端服务。

---

## 🎯 目标

1. **配置 Supabase 项目**
   - 创建数据表结构
   - 配置 Row Level Security (RLS)
   - 设置实时订阅

2. **后端集成**
   - 安装 Supabase Python SDK
   - 实现真实的云端上传/下载
   - 处理认证和权限

3. **前端集成**
   - 安装 Supabase JS SDK
   - 实现实时同步
   - 优化用户体验

---

## 🗄️ Supabase 数据库设计

### 表结构

#### 1. `cloud_capsules` - 云端胶囊表
```sql
CREATE TABLE cloud_capsules (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users NOT NULL,
  local_id INTEGER, -- 本地数据库 ID

  -- 胶囊基本信息
  name TEXT NOT NULL,
  description TEXT,
  capsule_type_id INTEGER,
  reaper_project_path TEXT,

  -- 时间戳
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  last_write_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  deleted_at TIMESTAMP WITH TIME ZONE, -- 软删除

  -- 版本控制
  version INTEGER DEFAULT 1,
  data_hash TEXT, -- SHA256 哈希

  -- 元数据
  metadata JSONB,

  -- 索引
  UNIQUE(user_id, local_id)
);

-- 索引
CREATE INDEX idx_cloud_capsules_user_id ON cloud_capsules(user_id);
CREATE INDEX idx_cloud_capsules_local_id ON cloud_capsules(local_id);
CREATE INDEX idx_cloud_capsules_updated_at ON cloud_capsules(updated_at);
```

#### 2. `cloud_capsule_tags` - 云端标签表
```sql
CREATE TABLE cloud_capsule_tags (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users NOT NULL,
  capsule_id UUID REFERENCES cloud_capsules(id) ON DELETE CASCADE,

  lens_id TEXT,
  x REAL,
  y REAL,

  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  UNIQUE(user_id, capsule_id, lens_id)
);

CREATE INDEX idx_cloud_capsule_tags_user_id ON cloud_capsule_tags(user_id);
CREATE INDEX idx_cloud_capsule_tags_capsule_id ON cloud_capsule_tags(capsule_id);
```

#### 3. `cloud_capsule_coordinates` - 云端坐标表
```sql
CREATE TABLE cloud_capsule_coordinates (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users NOT NULL,
  capsule_id UUID REFERENCES cloud_capsules(id) ON DELETE CASCADE,

  lens_id TEXT,
  dimension TEXT,
  value REAL,

  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  UNIQUE(user_id, capsule_id, lens_id, dimension)
);

CREATE INDEX idx_cloud_capsule_coordinates_user_id ON cloud_capsule_coordinates(user_id);
CREATE INDEX idx_cloud_capsule_coordinates_capsule_id ON cloud_capsule_coordinates(capsule_id);
```

#### 4. `sync_log_cloud` - 云端同步日志
```sql
CREATE TABLE sync_log_cloud (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users NOT NULL,

  table_name TEXT NOT NULL,
  operation TEXT NOT NULL, -- 'create', 'update', 'delete'
  record_id UUID NOT NULL,
  direction TEXT NOT NULL, -- 'to_cloud', 'from_cloud'

  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- 元数据
  metadata JSONB
);

CREATE INDEX idx_sync_log_cloud_user_id ON sync_log_cloud(user_id);
CREATE INDEX idx_sync_log_cloud_created_at ON sync_log_cloud(created_at);
```

---

## 🔐 Row Level Security (RLS) 策略

```sql
-- 启用 RLS
ALTER TABLE cloud_capsules ENABLE ROW LEVEL SECURITY;
ALTER TABLE cloud_capsule_tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE cloud_capsule_coordinates ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_log_cloud ENABLE ROW LEVEL SECURITY;

-- 策略：用户只能访问自己的数据
CREATE POLICY "Users can view own capsules"
  ON cloud_capsules
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own capsules"
  ON cloud_capsules
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own capsules"
  ON cloud_capsules
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own capsules"
  ON cloud_capsules
  FOR DELETE
  USING (auth.uid() = user_id);

-- 类似策略用于其他表...
```

---

## 📦 技术栈

### 后端
- **Supabase Python Client**: `supabase`
- **现有 Flask API** 保持不变

### 前端
- **Supabase JS Client**: `@supabase/supabase-js`
- **Realtime**: 实时数据同步

---

## 🔧 实施步骤

### Step 1: 配置 Supabase 项目
- [ ] 在 Supabase Dashboard 创建项目
- [ ] 获取 API 密钥
- [ ] 在 Supabase SQL Editor 执行表创建脚本
- [ ] 配置 RLS 策略

### Step 2: 后端集成
- [ ] 安装 Supabase Python SDK
- [ ] 创建 Supabase 客户端配置
- [ ] 实现云端上传逻辑
- [ ] 实现云端下载逻辑
- [ ] 处理冲突检测

### Step 3: 前端集成
- [ ] 安装 Supabase JS SDK
- [ ] 创建 Supabase 客户端配置
- [ ] 实现实时订阅
- [ ] 优化同步指示器

### Step 4: 测试
- [ ] 单用户同步测试
- [ ] 多设备同步测试
- [ ] 冲突解决测试
- [ ] 离线/在线切换测试

---

## 🔄 同步流程

### 上传流程
```
本地数据库 → 获取待同步记录
           → 上传到 Supabase
           → 标记为已同步
           → 记录同步日志
```

### 下载流程
```
Supabase → 查询云端变更 (WHERE updated_at > last_sync)
         → 下载到本地
         → 检测冲突
         → 解决冲突
         → 更新本地数据库
```

### 实时同步
```
Supabase Realtime → 监听表变更
                  → 推送到前端
                  → 自动更新本地
```

---

## 📁 文件结构

```
synesth/
├── data-pipeline/
│   ├── supabase_client.py      # Supabase 客户端配置
│   ├── cloud_sync_service.py    # 云端同步服务
│   └── capsule_api.py          # 现有 API（修改）
│
├── webapp/src/
│   ├── utils/
│   │   └── supabaseClient.js   # Supabase 客户端配置
│   ├── contexts/
│   │   └── SyncContext.jsx     # 修改（添加实时订阅）
│   └── components/
│       └── SyncIndicator.jsx   # 修改（显示实时状态）
│
└── docs/
    └── PHASE_C_COMPLETION_REPORT.md
```

---

## ⚠️ 注意事项

1. **认证**: 使用 Supabase Auth 或保持现有 JWT 认证
2. **安全性**: Service Role Key 仅用于后端，不要暴露到前端
3. **性能**: 使用批量操作减少 API 调用
4. **冲突**: 使用 last_write_at 时间戳解决冲突
5. **离线支持**: 本地数据库为主，云端为辅

---

## 🚀 下一步

等待用户提供：
1. Supabase 项目 URL
2. Supabase Anon Key
3. Supabase Service Role Key

然后开始实施！
