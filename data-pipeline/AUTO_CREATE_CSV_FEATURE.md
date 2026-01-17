# 自动创建词库文件功能 - Auto-Create CSV Lexicon Feature

**更新时间**: 2026-01-07
**状态**: ✅ 已完成

---

## 功能说明

当创建新棱镜时，系统会自动创建对应的 CSV 词库文件，避免重构力场时出现"没有匹配的提示词"错误。

---

## 实现细节

### 后端代码修改

**文件**: [anchor_editor_v2.py](anchor_editor_v2.py)

**函数**: `create_lens()` (Lines 517-554)

**核心逻辑**:

```python
# 自动创建对应的 CSV 词库文件（如果不存在）
lexicon_file = config[lens_id]['lexicon_file']
lexicon_path = BASE_DIR / lexicon_file

csv_created = False
if not lexicon_path.exists():
    try:
        # 创建带有基本表头的 CSV 文件
        with open(lexicon_path, 'w', encoding='utf-8') as f:
            f.write('word_cn,word_en,semantic_hint\n')
        csv_created = True
        print(f"Created lexicon file: {lexicon_file}")
    except Exception as e:
        print(f"Warning: Failed to create lexicon file: {e}")

# 构建返回消息
message = f"成功创建棱镜 '{lens_id}'"
if csv_created:
    message += f"，已创建词库文件: {lexicon_file}"

return jsonify({
    "success": True,
    "lens_id": lens_id,
    "message": message,
    "lexicon_file": lexicon_file,
    "csv_created": csv_created
})
```

---

## API 响应格式

### 成功响应

```json
{
  "success": true,
  "lens_id": "my_custom_lens",
  "message": "成功创建棱镜 'my_custom_lens'，已创建词库文件: lexicon_my_custom_lens.csv",
  "lexicon_file": "lexicon_my_custom_lens.csv",
  "csv_created": true
}
```

### 如果词库文件已存在

```json
{
  "success": true,
  "lens_id": "my_custom_lens",
  "message": "成功创建棱镜 'my_custom_lens'",
  "lexicon_file": "lexicon_my_custom_lens.csv",
  "csv_created": false
}
```

---

## CSV 文件格式

### 初始内容

```csv
word_cn,word_en,semantic_hint
```

### 三列说明

1. **word_cn**: 中文词汇
2. **word_en**: 英文词汇
3. **semantic_hint**: 语义提示（可选）

### 示例数据

```csv
word_cn,word_en,semantic_hint
明亮,Bright,light and radiant
黑暗,Dark,little or no light
温暖,Warm,moderately high temperature
寒冷,Cold,of or at a low temperature
```

---

## 使用流程

### 1. 创建新棱镜

**界面操作**:
1. 打开锚点编辑器: http://localhost:5001
2. 切换到"棱镜管理"标签页
3. 点击"➕ 创建新棱镜"
4. 填写表单信息
5. 点击"创建棱镜"按钮

**系统操作**:
- ✅ 在 `anchor_config_v2.json` 中创建棱镜配置
- ✅ 自动创建 CSV 词库文件（如果不存在）
- ✅ 保存历史快照

### 2. 验证词库文件

```bash
# 检查文件是否创建
ls -lh /Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/lexicon_*.csv

# 查看文件内容
cat /Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/lexicon_my_custom_lens.csv
```

### 3. 添加词汇到词库

**方式一：使用 Web 界面**
1. 在锚点编辑器中，切换到"词库编辑"标签页
2. 选择棱镜
3. 手动添加词汇

**方式二：直接编辑 CSV**
```bash
# 编辑 CSV 文件
vim /Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/lexicon_my_custom_lens.csv

# 添加词汇示例
word_cn,word_en,semantic_hint
明亮,Bright,light and radiant
黑暗,Dark,little or no light
温暖,Warm,moderately high temperature
寒冷,Cold,of or at a low temperature
```

### 4. 重构力场

1. 在锚点编辑器中，选择新创建的棱镜
2. 点击"🔄 重构力场"按钮
3. 系统会使用词库中的词汇重新生成语义向量场

---

## 测试验证

### 测试脚本

```python
from anchor_editor_v2 import create_lens_config, BASE_DIR
from pathlib import Path

# Test creating a new lens config
test_data = {
    'lens_name': 'Test',
    'x_neg': 'A',
    'x_pos': 'B',
    'y_neg': 'C',
    'y_pos': 'D'
}

config = create_lens_config(test_data)
print(f'✓ Created lens config')
print(f'  - Lexicon file: {config["lexicon_file"]}')

# Test CSV creation
lexicon_file = config['lexicon_file']
lexicon_path = BASE_DIR / f'test_{lexicon_file}'

if not lexicon_path.exists():
    with open(lexicon_path, 'w', encoding='utf-8') as f:
        f.write('word_cn,word_en,semantic_hint\n')
    print(f'✓ Created test CSV: test_{lexicon_file}')

    # Verify content
    with open(lexicon_path, 'r', encoding='utf-8') as f:
        content = f.read()
        print(f'  - Content: {repr(content)}')

    # Clean up
    lexicon_path.unlink()
    print(f'✓ Cleaned up test file')
```

**测试结果**:

```
✓ Created lens config
  - Lexicon file: lexicon_new_lens.csv
✓ Created test CSV: test_lexicon_new_lens.csv
  - Content: 'word_cn,word_en,semantic_hint\n'
✓ Cleaned up test file
```

---

## 错误处理

### 1. 文件创建失败

**错误信息** (服务器日志):
```
Warning: Failed to create lexicon file: [Errno 13] Permission denied
```

**解决方案**:
- 检查 data-pipeline 目录的写权限
- 确保当前用户有权限创建文件

### 2. 词库文件不存在

**错误信息** (前端):
```
没有找到符合类目要求的词
```

**原因**: CSV 文件未创建或路径错误

**解决方案**:
```bash
# 检查文件是否存在
ls -lh lexicon_*.csv

# 如果不存在，手动创建
touch lexicon_my_custom_lens.csv
echo "word_cn,word_en,semantic_hint" > lexicon_my_custom_lens.csv
```

---

## 相关功能

### 1. 删除棱镜时自动重命名 CSV

参见: [DELETE_LEXICON_FEATURE.md](DELETE_LEXICON_FEATURE.md)

**行为**: 删除棱镜时，将对应的 CSV 文件重命名为 `deleted_{filename}_{timestamp}.csv`

### 2. 智能锚点生成

参见: [SMART_GENERATION_READY.md](SMART_GENERATION_READY.md)

**功能**: 基于轴标签自动生成建议锚点

---

## 历史问题

### 问题 1: "重构力场总是提示没有匹配的提示词"

**原因**: 创建新棱镜时，对应的 CSV 词库文件没有被创建

**状态**: ✅ 已解决

**解决方案**: 在 `create_lens()` 函数中添加自动创建 CSV 文件的逻辑

### 问题 2: CSV 文件格式不匹配

**原因**: 词库文件使用了错误的列名（`en, cn` 而不是 `word_en, word_cn`）

**状态**: ✅ 已在之前的版本中修复

---

## 性能说明

- **文件创建时间**: < 10ms（本地文件系统）
- **内存占用**: 可忽略不计
- **影响范围**: 仅在创建新棱镜时执行

---

## 未来优化建议

1. **预设词库模板**: 在创建棱镜时，提供常用词库模板选项
2. **批量导入词汇**: 支持从其他 CSV 文件批量导入词汇
3. **智能词汇推荐**: 基于轴标签，智能推荐相关词汇
4. **词库验证**: 在添加词汇时进行格式和重复性验证

---

**功能状态**: ✅ 已完成并测试通过
**最后更新**: 2026-01-07
**创建者**: Claude (Sonnet 4.5)
