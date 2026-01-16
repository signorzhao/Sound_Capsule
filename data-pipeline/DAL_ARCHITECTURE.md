# 数据访问层 (DAL) 架构说明

**日期**: 2026-01-11
**状态**: ✅ 架构清晰

---

## 📊 架构层次

```
┌─────────────────────────────────────────────────────────┐
│  业务逻辑层 (Business Logic Layer)                       │
│  - capsule_api.py (Flask routes)                        │
│  - sync_service.py (同步服务)                            │
│  - manual_export_helper.py                              │
└────────────────┬────────────────────────────────────────┘
                 │ 调用 DAL 方法
                 ↓
┌─────────────────────────────────────────────────────────┐
│  数据访问层 (Data Access Layer - DAL)                    │
│                                                         │
│  1. 通用 DAL (Generic DAL)                               │
│     - supabase_client.py (SupabaseClient)               │
│       • upload_capsule()                                 │
│       • download_capsules()                             │
│       • upload_file()                                   │
│       • download_file()                                 │
│                                                         │
│  2. 专用 DAL (Specialized DAL)                           │
│     - dal_cloud_prisms.py (CloudPrismDAL)               │
│       • upload_prism()                                  │
│       • download_prisms()                               │
│       • sync_prism()                                    │
└────────────────┬────────────────────────────────────────┘
                 │ 直接使用 Supabase SDK
                 ↓
┌─────────────────────────────────────────────────────────┐
│  Supabase Python SDK                                     │
│  - client.table()                                       │
│  - client.storage()                                     │
└─────────────────────────────────────────────────────────┘
```

---

## ✅ 正确的调用模式

### ❌ 错误示例（业务逻辑层直接调用 SDK）

```python
# capsule_api.py
@app.route('/api/sync/upload', methods=['POST'])
def sync_upload():
    from supabase_client import get_supabase_client

    supabase = get_supabase_client()

    # ❌ 业务逻辑层直接调用 Supabase SDK
    result = supabase.client.table('cloud_capsules').insert(data).execute()

    return jsonify(result)
```

### ✅ 正确示例（业务逻辑层调用 DAL）

```python
# capsule_api.py
@app.route('/api/sync/upload', methods=['POST'])
def sync_upload():
    from supabase_client import get_supabase_client

    supabase = get_supabase_client()

    # ✅ 业务逻辑层调用 DAL 方法
    result = supabase.upload_capsule(user_id, capsule_data)

    return jsonify(result)
```

---

## 📁 DAL 层分类

### 1. 通用 DAL (supabase_client.py)

**职责**:
- 封装 Supabase SDK 操作
- 提供通用的 CRUD 方法
- 处理文件上传/下载
- 管理 Supabase 客户端生命周期

**关键方法**:
```python
class SupabaseClient:
    def upload_capsule(self, user_id, capsule_data)
    def download_capsules(self, user_id, since=None)
    def delete_capsule(self, user_id, local_id)
    def upload_file(self, bucket, path, file)
    def download_file(self, bucket, path)
```

**设计特点**:
- ✅ **可以在内部使用 `self.client.table()`** - 这是 DAL 层的职责
- ✅ 对外提供高级抽象方法
- ✅ 处理错误、重试、日志

### 2. 专用 DAL (dal_cloud_prisms.py)

**职责**:
- 专门处理 prism 配置同步
- 实现版本比较逻辑
- 处理 Last Write Wins 冲突解决

**关键方法**:
```python
class CloudPrismDAL:
    def upload_prism(self, user_id, prism_id, prism_data)
    def download_prisms(self, user_id)
    def sync_prism(self, user_id, local_prism)  # 智能版本比较
    def batch_upload_prisms(self, user_id, prisms)
```

**设计特点**:
- ✅ **可以在内部使用 `self.client.table()`** - 这是 DAL 层的职责
- ✅ 专注于棱镜同步业务逻辑
- ✅ 提供批量操作和智能同步

---

## 🎯 封装原则

### ✅ 允许的操作

| 层次 | 允许调用 | 示例 |
|------|---------|------|
| 业务逻辑层 | DAL 方法 | `supabase.upload_capsule()` |
| DAL 层 | Supabase SDK | `self.client.table().insert()` |

### ❌ 禁止的操作

| 层次 | 禁止调用 | 错误示例 |
|------|---------|---------|
| 业务逻辑层 | Supabase SDK | `supabase.client.table()` |

---

## 📊 当前架构状态

### ✅ 已正确封装的模块

1. **capsule_api.py**
   - ✅ 调用 `supabase.upload_capsule()`
   - ✅ 调用 `supabase.download_capsules()`
   - ✅ 没有直接使用 `supabase.client.table()`

2. **sync_service.py**
   - ✅ 调用 `prism_dal.upload_prism()`
   - ✅ 调用 `prism_dal.download_prisms()`
   - ✅ 没有直接使用 `supabase.client.table()`

### ✅ DAL 层实现

1. **supabase_client.py** (通用 DAL)
   - ✅ 封装 Supabase SDK 操作
   - ✅ 提供高级抽象方法
   - ✅ 内部使用 `self.client.table()` - **这是正确的**

2. **dal_cloud_prisms.py** (专用 DAL)
   - ✅ 专门处理棱镜同步
   - ✅ 内部使用 `self.client.table()` - **这是正确的**

---

## 🔄 架构优势

### 1. 解耦

**好处**:
- 业务逻辑层不需要了解 Supabase SDK 细节
- 更换云服务提供商只需修改 DAL 层
- 业务逻辑测试更容易（mock DAL）

### 2. 复用

**好处**:
- DAL 方法可以在多个业务逻辑中复用
- 避免重复的 Supabase 操作代码
- 统一的错误处理和日志

### 3. 维护性

**好处**:
- Supabase SDK 升级只需修改 DAL 层
- 业务逻辑代码更简洁
- 清晰的职责划分

---

## 📋 未来扩展建议

### 如果需要更换云服务提供商

假设从 Supabase 迁移到 AWS S3 + DynamoDB：

**步骤 1**: 实现 AWS DAL
```python
# aws_client.py
class AWSClient:
    def upload_capsule(self, user_id, capsule_data):
        # 使用 boto3 上传到 S3 + DynamoDB
        pass

    def download_capsules(self, user_id, since=None):
        # 从 DynamoDB 查询
        pass
```

**步骤 2**: 更新业务逻辑层
```python
# capsule_api.py
@app.route('/api/sync/upload', methods=['POST'])
def sync_upload():
    # 只需修改导入
    # from supabase_client import get_supabase_client  # 旧
    from aws_client import get_aws_client              # 新

    client = get_aws_client()
    result = client.upload_capsule(user_id, capsule_data)

    return jsonify(result)
```

**无需修改业务逻辑** - 只需替换 DAL 实现！

---

## 🎯 总结

### 当前架构状态

✅ **架构清晰，封装良好**

- 业务逻辑层（capsule_api.py, sync_service.py）正确调用 DAL 方法
- DAL 层（supabase_client.py, dal_cloud_prisms.py）正确封装 Supabase SDK
- 没有违反封装原则的代码

### 关键原则

1. **业务逻辑层** 不直接使用 Supabase SDK
2. **DAL 层** 可以使用 `self.client.table()` - 这是它的职责
3. **DAL 方法** 提供高级抽象，隐藏 SDK 细节

### 设计模式

- **Repository Pattern**: DAL 层实现数据访问仓储
- **Dependency Injection**: 业务逻辑层注入 DAL 实例
- **Single Responsibility**: 每层只负责自己的职责

---

**文档版本**: 1.0
**最后更新**: 2026-01-11
**状态**: ✅ 架构验证通过
