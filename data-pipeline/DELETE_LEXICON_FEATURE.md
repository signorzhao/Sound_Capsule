# 删除棱镜时自动重命名词库文件

**功能说明**: 当在编辑器中删除棱镜时，系统会自动重命名对应的 CSV 词库文件，避免数据丢失。

---

## 功能特性

### 自动重命名规则

当删除棱镜时（例如删除 `mechanics` 棱镜）：

**原始文件**: `lexicon_mechanics.csv`

**重命名后**: `deleted_lexicon_mechanics_20260107_004240.csv`

格式：`deleted_{原始文件名}_{时间戳}.csv`

时间戳格式：`YYYYMMDD_HHMMSS`（年月日_时分秒）

---

## 示例

### 删除前

```
data-pipeline/
├── lexicon_texture.csv
├── lexicon_mechanics.csv      # 38 个词
├── lexicon_source.csv
└── lexicon_temperament.csv
```

### 删除 mechanics 棱镜后

```
data-pipeline/
├── lexicon_texture.csv
├── deleted_lexicon_mechanics_20260107_004240.csv  # 已重命名
├── lexicon_source.csv
└── lexicon_temperament.csv
```

---

## 实现细节

### 后端逻辑

**文件**: `anchor_editor_v2.py`

**函数**: `delete_lens(lens_id)`

**流程**:

1. 加载配置并检查棱镜是否存在
2. 保存历史快照（如果有）
3. **获取词库文件名**：`lexicon_file = config[lens_id].get('lexicon_file')`
4. **检查文件是否存在**
5. **生成新文件名**：
   ```python
   timestamp = time.strftime('%Y%m%d_%H%M%S')
   new_filename = f"deleted_{lexicon_path.stem}_{timestamp}.csv"
   ```
6. **重命名文件**：`lexicon_path.rename(new_path)`
7. 删除棱镜配置
8. 返回成功消息（包含重命名后的文件名）

---

## 前端交互

### 删除确认对话框

```javascript
async function confirmDeleteLens(lens_id) {
    if (!confirm(`确定要删除棱镜 "${lens_id}" 吗？\n\n注意：胶囊的标签数据将被保留（孤儿标签机制）。`)) {
        return;
    }

    try {
        const res = await fetch(`/api/lenses/${lens_id}`, {
            method: 'DELETE'
        });

        const result = await res.json();

        if (result.success) {
            // 显示成功消息
            showToast(`✅ ${result.message}`);
            // 如果词库文件被重命名，result.renamed_lexicon 会包含新文件名
        }
    } catch (error) {
        showToast(`❌ 删除失败: ${error}`, true);
    }
}
```

### 成功消息示例

**无词库文件**:
```
✅ 成功删除棱镜 'mechanics'
```

**有词库文件（已重命名）**:
```
✅ 成功删除棱镜 'mechanics'，词库文件已重命名为: deleted_lexicon_mechanics_20260107_004240.csv
```

---

## 错误处理

### 如果词库文件不存在

系统会跳过重命名步骤，只删除棱镜配置，不会报错。

### 如果重命名失败

系统会在控制台输出警告：
```
Warning: Failed to rename lexicon file: [错误信息]
```

但删除操作会继续完成，不会中断。

---

## 恢复已删除的词库

如果需要恢复已删除的词库文件：

1. 找到重命名后的文件（例如 `deleted_lexicon_mechanics_20260107_004240.csv`）
2. 重命名回原始名称（例如 `lexicon_mechanics.csv`）
3. 重新创建棱镜并指定该词库文件

```bash
# 示例：恢复词库文件
cd /Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline
mv deleted_lexicon_mechanics_20260107_004240.csv lexicon_mechanics.csv
```

---

## 注意事项

1. **不会永久删除**：词库文件只是被重命名，不会丢失
2. **时间戳确保唯一性**：每次删除都会生成不同的文件名
3. **手动创建的文件不受影响**：如果棱镜使用的是 `master_lexicon_v3.csv`，该文件不会被重命名（因为是共享词库）
4. **历史快照独立保存**：词库文件重命名与历史快照是两个独立的机制

---

## 测试

### 测试步骤

1. 创建一个测试棱镜（例如 `test_lens`）
2. 系统会自动创建 `lexicon_test_lens.csv`
3. 在编辑器中删除 `test_lens`
4. 验证：
   - ✅ 棱镜从配置中删除
   - ✅ CSV 文件被重命名为 `deleted_lexicon_test_lens_YYYYMMDD_HHMMSS.csv`
   - ✅ 前端显示成功消息

---

## 相关文件

- **后端**: `anchor_editor_v2.py` (line 540-605)
- **前端**: 内嵌在 `HTML_TEMPLATE` 中 (line 1077-1099)
- **配置**: `anchor_config_v2.json`

---

**创建时间**: 2026-01-07
**版本**: v1.0
**作者**: Claude (Sonnet 4.5)
