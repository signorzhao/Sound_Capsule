# 用户配置变更和多用户下载问题分析

**日期**: 2026-01-12  
**问题**: 
1. 更换导出目录后，能否正常上传和下载？
2. 更换用户名后，能否下载其他用户的胶囊完整数据？

---

## 🔍 问题 1: 更换导出目录

### 当前实现分析

#### ✅ 已支持的功能
1. **动态读取配置**：
   ```python
   # capsule_api.py - get_capsules() 和 get_capsule()
   user_config = load_user_config()
   export_base = Path(user_config.get('export_dir', EXPORT_DIR))
   rpp_path = export_base / capsule['file_path'] / capsule['rpp_file']
   capsule['local_rpp_path'] = str(rpp_path.resolve())
   ```

2. **下载时使用新目录**：
   ```python
   # capsule_download_api.py
   user_config = load_user_config()
   export_dir = user_config.get('export_dir', 'output')
   local_capsule_path = Path(export_dir) / file_path
   ```

#### ⚠️ 潜在问题

**场景**：
- 用户初始导出目录：`/Users/ianzhao/Documents/old_folder`
- 胶囊 ID 43 的文件在：`/Users/ianzhao/Documents/old_folder/impact_ianzhao_20260112_142111/`
- 用户更改导出目录为：`/Users/ianzhao/Documents/new_folder`
- 数据库中的 `file_path` 仍然是：`impact_ianzhao_20260112_142111`（相对路径）

**问题**：
1. ✅ **新下载的文件**：会保存到新目录 ✅
2. ❌ **旧胶囊的 `local_rpp_path`**：会指向新目录，但文件实际在旧目录
3. ❌ **打开旧胶囊**：会失败，因为新目录中没有文件

### 🔧 修复方案

#### 方案 A: 文件存在性检查（推荐）
在 `get_capsules` 和 `get_capsule` 中添加文件存在性检查：

```python
# 在 capsule_api.py 中修改
for capsule in capsules:
    if capsule.get('file_path') and capsule.get('rpp_file'):
        user_config = load_user_config()
        export_base = Path(user_config.get('export_dir', EXPORT_DIR))
        rpp_path = export_base / capsule['file_path'] / capsule['rpp_file']
        
        # 检查文件是否存在
        if rpp_path.exists():
            capsule['local_rpp_path'] = str(rpp_path.resolve())
            capsule['file_exists'] = True
        else:
            # 尝试从旧目录查找（如果配置了）
            # 或者标记为文件不存在
            capsule['local_rpp_path'] = str(rpp_path.resolve())
            capsule['file_exists'] = False
            logger.warning(f"[PATH] 文件不存在: {rpp_path}")
```

#### 方案 B: 多目录搜索（更完善）
在 `get_capsules` 中实现多目录搜索：

```python
def find_capsule_file(capsule, file_type='rpp'):
    """在多个可能的目录中查找胶囊文件"""
    user_config = load_user_config()
    current_export_dir = Path(user_config.get('export_dir', EXPORT_DIR))
    
    # 可能的目录列表
    possible_dirs = [
        current_export_dir,  # 当前配置的目录
        Path('output'),  # 默认目录
        # 可以从历史配置中读取（如果保存了）
    ]
    
    for base_dir in possible_dirs:
        file_path = base_dir / capsule['file_path'] / capsule.get('rpp_file' if file_type == 'rpp' else 'preview_audio')
        if file_path.exists():
            return str(file_path.resolve())
    
    # 如果都找不到，返回当前配置的路径（即使不存在）
    return str(current_export_dir / capsule['file_path'] / capsule.get('rpp_file'))
```

---

## 🔍 问题 2: 跨用户下载

### 当前实现分析

#### ❌ 当前问题
```python
# capsule_download_api.py - download_capsule_assets()
# 使用当前登录用户的 supabase_user_id
actual_supabase_user_id = current_user.get('supabase_user_id')

# 下载时使用当前用户的 ID
supabase.download_file(
    user_id=actual_supabase_user_id,  # ❌ 错误！应该是胶囊原作者的 ID
    capsule_folder_name=capsule_dir_name,
    file_type='audio_folder',
    local_path=str(local_capsule_path)
)
```

**问题场景**：
- 用户 A (`supabase_user_id: user-a-uuid`) 创建了胶囊
- 用户 B (`supabase_user_id: user-b-uuid`) 登录后尝试下载
- 代码使用 `user-b-uuid` 去访问 `capsule-files/user-b-uuid/...`
- 但实际文件在 `capsule-files/user-a-uuid/...`
- **结果**：找不到文件 ❌

#### ✅ 参考实现（sync/download API）
```python
# capsule_api.py - download_from_cloud()
# 重要：使用云端记录中的原作者 user_id
owner_id = record.get('user_id')  # 从云端记录获取
if not owner_id:
    owner_id = user_id  # 如果没有，使用当前用户

supabase.download_file(owner_id, ...)  # ✅ 使用原作者 ID
```

### 🔧 修复方案

#### 方案 A: 从 cloud_capsules 表查询（推荐）
需要查询云端表获取胶囊的原作者：

```python
# 在 capsule_download_api.py 中修改
def download_capsule_assets(capsule_id):
    # ... 现有代码 ...
    
    capsule = db.get_capsule(capsule_id)
    cloud_id = capsule.get('cloud_id')  # 胶囊的云端 UUID
    
    # 查询云端表获取原作者信息
    actual_supabase_user_id = None
    
    if cloud_id:
        # 从 Supabase 查询胶囊的原作者
        try:
            supabase = get_supabase_client()
            cloud_capsule = supabase.client.table('cloud_capsules').select('user_id').eq('id', cloud_id).single().execute()
            
            if cloud_capsule.data:
                owner_user_id = cloud_capsule.data.get('user_id')
                # 查询本地 users 表，找到对应的 supabase_user_id
                conn = db.connect()
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT supabase_user_id FROM users WHERE supabase_user_id = ? LIMIT 1", (owner_user_id,))
                    users = cursor.fetchall()
                    if users and users[0][0]:
                        actual_supabase_user_id = users[0][0]
                        logger.info(f"[DOWNLOAD] 胶囊原作者 Supabase User ID: {actual_supabase_user_id}")
                finally:
                    db.close()
        except Exception as e:
            logger.warning(f"[DOWNLOAD] 无法查询胶囊原作者: {e}")
    
    # 如果查询失败，使用当前登录用户（向后兼容）
    if not actual_supabase_user_id:
        if user_id:
            user = db.get_user_by_id(user_id)
            if user:
                actual_supabase_user_id = user.get('supabase_user_id')
        
        if not actual_supabase_user_id:
            # 使用默认用户（开发环境）
            conn = db.connect()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT supabase_user_id FROM users LIMIT 1")
                users = cursor.fetchall()
                if users and users[0][0]:
                    actual_supabase_user_id = users[0][0]
            finally:
                db.close()
    
    # 使用正确的用户 ID 下载
    success = supabase.download_file(
        user_id=actual_supabase_user_id,  # ✅ 使用原作者 ID
        capsule_folder_name=capsule_dir_name,
        file_type='audio_folder',
        local_path=str(local_capsule_path)
    )
```

#### 方案 B: 在本地数据库存储原作者信息（更高效）
在 `capsules` 表中添加 `owner_supabase_user_id` 字段：

```sql
-- 添加原作者 Supabase User ID 字段
ALTER TABLE capsules ADD COLUMN owner_supabase_user_id TEXT;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_capsules_owner_user_id ON capsules(owner_supabase_user_id);
```

然后在同步时保存：
```python
# 在 sync/download API 中
owner_id = record.get('user_id')
# 保存到本地数据库
db.update_capsule(capsule_id, {'owner_supabase_user_id': owner_id})
```

下载时直接使用：
```python
# 在 capsule_download_api.py 中
owner_id = capsule.get('owner_supabase_user_id') or actual_supabase_user_id
```

---

## 📊 优先级建议

### 🔴 高优先级：问题 2（跨用户下载）
**影响**：如果用户切换账号，无法下载其他用户的胶囊  
**修复难度**：中等  
**建议**：立即修复

### 🟡 中优先级：问题 1（导出目录变更）
**影响**：如果用户更改导出目录，旧胶囊可能无法打开  
**修复难度**：低  
**建议**：添加文件存在性检查，前端显示警告

---

## 🧪 测试计划

### 测试 1: 导出目录变更
1. 创建胶囊，导出目录为 `/old/path`
2. 更改用户配置，导出目录为 `/new/path`
3. 尝试打开旧胶囊
4. **预期**：应该能找到文件（如果文件还在旧目录）或显示警告

### 测试 2: 跨用户下载
1. 用户 A 创建并上传胶囊
2. 用户 B 登录
3. 用户 B 尝试下载用户 A 的胶囊
4. **预期**：应该能成功下载（使用用户 A 的 Supabase User ID）

---

## 📝 实施建议

### 第一步：修复跨用户下载（问题 2）
1. 修改 `capsule_download_api.py`，从云端查询胶囊原作者
2. 使用原作者的 `supabase_user_id` 下载文件
3. 测试验证

### 第二步：增强路径处理（问题 1）
1. 在 `get_capsules` 和 `get_capsule` 中添加文件存在性检查
2. 前端显示文件不存在警告
3. （可选）实现多目录搜索

---

**下一步**：请确认是否立即实施这些修复？
