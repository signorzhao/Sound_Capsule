# 功能验证指南

**日期**: 2026-01-07
**服务器状态**: ✅ 已重启（运行新代码）

---

## ⚠️ 重要：刷新浏览器

服务器已重启以加载新代码，**你必须刷新浏览器才能看到新功能**：

### Mac用户：
按 `Cmd + Shift + R` 强制刷新页面

### Windows用户：
按 `Ctrl + Shift + R` 强制刷新页面

---

## 功能 1: 词性筛选 ✅ 已实现

### 验证步骤：

1. **打开创建新棱镜界面**
   - 访问: http://localhost:5001
   - 点击"棱镜管理"标签页
   - 点击"➕ 创建新棱镜"

2. **查找词性选择器**
   - 在"智能功能"区域（🎲 生成建议锚点按钮上方）
   - 应该看到一个下拉框：
     ```
     词性筛选（可选）
     ┌────────────────────────┐
     │ 全部词性               │
     │ 名词 (Noun)            │
     │ 动词 (Verb)            │
     │ 形容词 (Adjective) ✓  │ ← 默认选中
     └────────────────────────┘
     💡 默认推荐形容词，适合描述音质和感受
     ```

3. **测试生成锚点**
   - 填写表单：
     - 棱镜 ID: `test_lens`
     - 棱镜名称: `测试棱镜`
     - X轴: `Dark / 黑暗` ← → `Light / 光明`
     - Y轴: `Cold / 寒冷` ← → `Warm / 温暖`
   - 选择词性: `形容词 (Adjective)`
   - 点击"🎲 生成建议锚点"
   - 应该看到：
     ```
     ✅ 生成了 20 个建议锚点（形容词）
     🎯 唯一词汇: 20 个（无重复）
     • Bright [adjective]
     • Cold [adjective]
     • Warm [adjective]
     ... 等 20 个
     ```

### 后端测试结果：

```
✅ 通过: 生成锚点(形容词)
   - 所有锚点都是形容词: True
   - 没有重复词汇: True

✅ 通过: 生成锚点(名词)
   - 所有锚点都是名词: True
   - 没有重复词汇: True
```

---

## 功能 2: 自动创建CSV文件 ✅ 已实现

### 验证步骤：

1. **创建新棱镜**
   - 在创建新棱镜表单中填写完整信息
   - 点击"创建棱镜"按钮

2. **检查成功消息**
   - 应该显示：
     ```
     ✅ 成功创建棱镜 'test_lens'，已创建词库文件: lexicon_test_lens.csv
     ```

3. **验证文件存在**
   ```bash
   ls -lh /Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/lexicon_test_lens.csv
   ```

4. **查看文件内容**
   ```bash
   cat /Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/lexicon_test_lens.csv
   ```
   应该看到：
   ```csv
   word_cn,word_en,semantic_hint
   ```

5. **测试重构力场**
   - 在锚点编辑器中选择新创建的棱镜
   - 点击"🔄 重构力场"按钮
   - 应该成功生成力场（不再提示"没有匹配的词"）

---

## 已知问题

### 问题 1: 浏览器缓存

**症状**: 刷新页面后仍然看不到词性选择器

**解决方案**:
1. 清除浏览器缓存
2. 或使用隐私/无痕模式打开
3. 或使用不同的浏览器

### 问题 2: CSV文件未创建

**症状**: 创建棱镜后CSV文件没有生成

**可能原因**:
- 服务器权限问题
- 磁盘空间不足

**检查方法**:
```bash
# 查看服务器日志
tail -50 /tmp/anchor_editor.log

# 检查目录权限
ls -ld /Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline
```

---

## 功能对比

| 功能 | 之前 | 现在 |
|------|------|------|
| 词性筛选 | ❌ 不可用 | ✅ 可选择名词/动词/形容词 |
| 词汇去重 | ❌ 可能有重复 | ✅ 强制全局唯一 |
| CSV创建 | ❌ 手动创建 | ✅ 自动创建 |
| 重构力场 | ❌ 提示"没有匹配的词" | ✅ 正常工作 |

---

## 完整测试流程

### 测试 1: 词性筛选

```
1. 刷新浏览器 (Cmd+Shift+R)
2. 创建新棱镜
3. 选择"形容词"
4. 生成锚点
5. 验证: 所有锚点都是形容词
6. 验证: 没有重复词汇
```

### 测试 2: CSV自动创建

```
1. 创建新棱镜（ID: test_123）
2. 检查响应消息
3. 验证CSV文件存在
4. 查看CSV内容
5. 测试重构力场
```

### 测试 3: 去重验证

```
1. 生成20个锚点
2. 检查响应中的 unique_words
3. 验证: unique_words = 20
```

---

## API 测试

### 测试词性筛选API:

```bash
curl -X POST http://localhost:5001/api/lenses/temp_preview/generate-anchors \
  -H "Content-Type: application/json" \
  -d '{
    "count_per_quadrant": 5,
    "pos_filter": ["adjective"],
    "axes": {
      "x_label": {"neg": "Dark", "pos": "Light"},
      "y_label": {"neg": "Cold", "pos": "Warm"}
    }
  }'
```

**预期响应**:
```json
{
  "success": true,
  "anchors": [...],
  "message": "成功生成 20 个建议锚点（形容词）",
  "pos_filter": ["adjective"],
  "unique_words": 20
}
```

---

## 下一步

如果刷新页面后仍然看不到词性选择器，请：

1. 告诉我你看到的界面是什么样的
2. 提供浏览器控制台的错误信息（按F12打开）
3. 我会帮你排查问题

---

**最后更新**: 2026-01-07
**服务器**: ✅ 运行中 (http://localhost:5001)
**代码版本**: ✅ 最新（已包含所有功能）
