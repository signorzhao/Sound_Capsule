# 胶囊标签API修复 - 支持新棱镜

**日期**: 2026-01-07
**问题**: 新建棱镜（如 mechanics）的标签无法保存到数据库

---

## 问题原因

在 `capsule_api.py` 的两个API端点中，有**硬编码的棱镜白名单**：

### 1. POST /api/capsules/{id}/tags (第427行)
```python
if tag['lens'] not in ['texture', 'source', 'materiality', 'temperament']:
    raise APIError(f"无效的棱镜类型: {tag['lens']}")
```

### 2. PUT /api/capsules/{id}/tags (第508行)
```python
if lens not in ['texture', 'source', 'materiality', 'temperament']:
    continue  # 跳过非棱镜字段
```

### 问题影响

当用户在WebUI中使用新棱镜（如 `mechanics`）编辑胶囊标签并保存时：
- WebUI成功调用API发送数据
- API验证棱镜类型时失败（或直接跳过）
- 新棱镜的标签被拒绝或忽略
- 数据库中只有4个旧棱镜的标签

---

## 解决方案

### 修改策略

不再使用硬编码的棱镜白名单，而是**动态判断**字段是否为棱镜数据。

### 判断逻辑

1. **类型检查**: 字段值必须是数组
2. **字段名检查**: 排除已知的非棱镜字段

```python
for lens, tags in data.items():
    # 动态判断是否为棱镜字段
    if not isinstance(tags, list):
        continue  # 不是数组，跳过

    # 跳过已知的非棱镜字段
    if lens in ['capsule_type', 'name', 'description', 'metadata', 'created_at', 'updated_at']:
        continue

    # 处理棱镜标签
    for tag in tags:
        all_tags.append({
            'lens': lens,
            'word_id': tag.get('id', ''),
            'word_cn': tag.get('cn') or tag.get('zh') or tag.get('word', ''),
            'word_en': tag.get('en') or tag.get('word', ''),
            'x': tag.get('x', 0),
            'y': tag.get('y', 0)
        })
```

---

## 修改的文件

**文件**: `data-pipeline/capsule_api.py`

### 修改1: POST 接口 (第422-437行)

**之前**:
```python
if tag['lens'] not in ['texture', 'source', 'materiality', 'temperament']:
    raise APIError(f"无效的棱镜类型: {tag['lens']}")
```

**之后**:
```python
# 不再限制棱镜类型，允许任何棱镜（包括新创建的 mechanics 等）
```

### 修改2: POST 接口 - 格式2 (第439-460行)

**之前**:
```python
for lens, tags in data.items():
    if lens not in ['texture', 'source', 'materiality', 'temperament']:
        continue  # 跳过非棱镜字段
```

**之后**:
```python
for lens, tags in data.items():
    # 动态判断是否为棱镜字段
    if not isinstance(tags, list):
        continue  # 不是数组，跳过

    # 跳过已知的非棱镜字段
    if lens in ['capsule_type', 'name', 'description', 'metadata', 'created_at', 'updated_at']:
        continue
```

### 修改3: PUT 接口 (第506-521行)

应用了相同的动态判断逻辑。

---

## 优势

### 1. 完全向后兼容
- 原有的4个棱镜继续正常工作
- 不影响现有数据和功能

### 2. 自动支持新棱镜
- 创建新棱镜后无需修改API代码
- 新棱镜的标签可以立即保存
- 数据库会包含所有棱镜的标签

### 3. 更好的错误处理
- 不会因为棱镜类型不匹配而拒绝请求
- 使用类型检查而非名称白名单，更健壮

---

## 测试验证

### 测试步骤

1. **准备测试胶囊**
   ```bash
   # 查看现有胶囊
   sqlite3 database/capsules.db "SELECT id, name FROM capsules LIMIT 1;"
   ```

2. **使用新棱镜保存标签**
   ```bash
   curl -X PUT http://localhost:5002/api/capsules/1/tags \
     -H "Content-Type: application/json" \
     -d '{
       "mechanics": [
         {"id": "w1", "zh": "沉重", "en": "Heavy", "x": 10, "y": 20},
         {"id": "w2", "zh": "轻柔", "en": "Light", "x": 80, "y": 70}
       ]
     }'
   ```

3. **验证数据库**
   ```bash
   sqlite3 database/capsules.db "SELECT lens, word_cn FROM capsule_tags WHERE lens='mechanics';"
   ```

   应该能看到：
   ```
   mechanics|沉重
   mechanics|轻柔
   ```

4. **在WebUI中验证**
   - 打开胶囊库
   - 查看该胶囊的标签
   - 应该能看到绿色的 mechanics 标签

---

## 数据库验证

### 修复前
```sql
SELECT lens, COUNT(*) FROM capsule_tags GROUP BY lens;
```
```
materiality|16
source|17
temperament|23
texture|29
-- 缺少 mechanics!
```

### 修复后（预期）
```sql
SELECT lens, COUNT(*) FROM capsule_tags GROUP BY lens;
```
```
materiality|16
mechanics|2     -- 新增！
source|17
temperament|23
texture|29
```

---

## 工作流程

### 完整的标签保存流程

1. **用户在WebUI中编辑标签**
   - 选择新棱镜 `mechanics`
   - 添加标签：{"沉重", "轻柔", ...}
   - 点击保存

2. **WebUI发送PUT请求**
   ```javascript
   fetch(`/api/capsules/${capsuleId}/tags`, {
     method: 'PUT',
     body: JSON.stringify({
       mechanics: [
         {id: 'w1', zh: '沉重', en: 'Heavy', x: 10, y: 20}
       ]
     })
   })
   ```

3. **API接收并处理**
   - 检测到 `mechanics` 字段
   - 确认值是数组，不是特殊字段
   - 处理标签数据
   - 保存到数据库

4. **数据库更新**
   ```sql
   INSERT INTO capsule_tags (capsule_id, lens, word_id, word_cn, ...)
   VALUES (1, 'mechanics', 'w1', '沉重', ...);
   ```

5. **WebUI显示**
   - 从数据库加载标签
   - `lensNames['mechanics']` = '力学'
   - `lensColors['mechanics']` = '绿色主题'
   - 标签正确显示

---

## 后续优化建议

### 1. 棱镜注册表

在数据库中维护一个棱镜注册表：

```sql
CREATE TABLE registered_lenses (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    color TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. API验证增强

API可以查询注册表验证棱镜是否存在：

```python
def validate_lens(lens_id):
    db = get_database()
    registered = db.get_registered_lenses()
    return lens_id in [l['id'] for l in registered]
```

### 3. 自动发现新棱镜

当创建新棱镜时，自动注册到系统中：

```python
@app.route('/api/lenses', methods=['POST'])
def create_lens():
    # 创建棱镜...

    # 自动注册到胶囊系统
    db.register_lens(lens_id, lens_data)
```

---

## 修复状态

- [x] 问题诊断
- [x] POST接口修复
- [x] PUT接口修复
- [x] CapsuleLibrary.jsx显示修复
- [ ] 用户测试验证

---

## 注意事项

### 重启服务

修改API后需要重启胶囊API服务：

```bash
# 停止旧服务
pkill -f capsule_api

# 启动新服务
cd /Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline
python3 capsule_api.py
```

### 清除浏览器缓存

WebUI可能缓存了旧的标签数据，需要刷新：
- Mac: `Cmd + Shift + R`
- Windows: `Ctrl + Shift + R`

---

**最后更新**: 2026-01-07
**修复者**: Claude (Sonnet 4.5)
