# 胶囊类型管理 - 棱镜列表修复

**日期**: 2026-01-07
**问题**: 编辑胶囊类型时，优先棱镜下拉列表中看不到新建的棱镜（如 mechanics）

---

## 🔍 问题原因

### 硬编码的棱镜列表

在 `webapp/src/components/CapsuleTypeManager.jsx` 中，优先棱镜选择器是**硬编码**的：

```jsx
<select value={editingType.priority_lens} ...>
  <option value="texture">纹理 (Texture)</option>
  <option value="source">来源 (Source)</option>
  <option value="materiality">物质性 (Materiality)</option>
  <option value="temperament">性格 (Temperament)</option>
  {/* 缺少 mechanics！ */}
</select>
```

当在锚点编辑器中创建新棱镜（如 `mechanics`）时：
- ✅ 棱镜被添加到 `anchor_config_v2.json`
- ✅ API `/api/config` 会返回新棱镜
- ❌ 但WebUI的胶囊类型管理界面中看不到新棱镜（因为是硬编码）

---

## ✅ 解决方案

### 动态加载棱镜列表

修改 `CapsuleTypeManager.jsx`，从API动态加载可用的棱镜：

#### 1. 添加状态

```jsx
const [availableLenses, setAvailableLenses] = useState([]);
```

#### 2. 添加加载函数

```jsx
const loadAvailableLenses = async () => {
  try {
    const response = await fetch('http://localhost:5001/api/config');
    const config = await response.json();

    // 转换为选项格式
    const lensOptions = Object.keys(config).map(lensId => ({
      value: lensId,
      label: config[lensId].name || lensId,
      id: lensId
    }));

    setAvailableLenses(lensOptions);
  } catch (error) {
    console.error('加载棱镜列表失败:', error);
    // 使用默认列表作为后备
    setAvailableLenses([
      { value: 'texture', label: '纹理', id: 'texture' },
      { value: 'source', label: '来源', id: 'source' },
      { value: 'materiality', label: '物质性', id: 'materiality' },
      { value: 'temperament', label: '性格', id: 'temperament' },
      { value: 'mechanics', label: '力学', id: 'mechanics' }
    ]);
  }
};
```

#### 3. 在 useEffect 中调用

```jsx
useEffect(() => {
  loadCapsuleTypes();
  loadAvailableLenses();  // 新增
}, []);
```

#### 4. 使用动态列表渲染选项

```jsx
<select value={editingType.priority_lens} ...>
  {availableLenses.map(lens => (
    <option key={lens.value} value={lens.value}>
      {lens.label}
    </option>
  ))}
</select>
```

---

## 📋 修改的文件

**文件**: `webapp/src/components/CapsuleTypeManager.jsx`

**修改内容**:
1. 第 89 行：添加 `availableLenses` 状态
2. 第 91-116 行：添加 `loadAvailableLenses()` 函数
3. 第 140 行：在 `useEffect` 中调用加载函数
4. 第 459-472 行：使用动态列表替换硬编码选项

---

## 🎯 功能说明

### 优先棱镜的作用

在编辑胶囊类型时设置优先棱镜后：

1. **编辑胶囊标签**
   - 打开该类型胶囊的标签编辑界面
   - 默认选中所设置的优先棱镜

2. **导出到Reaper**
   - 导出到Reaper并跳转到棱镜编辑器时
   - 自动选中优先棱镜

### 示例

```
胶囊类型: MAGIC
优先棱镜: texture

操作流程:
1. 在WebUI中打开MAGIC类型的胶囊
2. 进入标签编辑界面
3. 自动选中"纹理(Texture)"棱镜
4. 可以切换到其他棱镜查看标签
```

---

## 🧪 测试验证

### 验证步骤

1. **启动服务**
   ```bash
   # 确保锚点编辑器在运行
   cd data-pipeline
   python3 anchor_editor_v2.py

   # 确保胶囊API在运行
   python3 capsule_api.py

   # 启动WebUI
   cd webapp
   npm run tauri dev
   ```

2. **查看现有棱镜**
   ```bash
   curl http://localhost:5001/api/config
   ```

   应该看到所有5个棱镜：
   - materiality
   - mechanics
   - source
   - temperament
   - texture

3. **在WebUI中测试**
   - 打开胶囊类型管理界面
   - 编辑任意胶囊类型
   - 查看"优先棱镜"下拉列表
   - 应该能看到所有5个棱镜

### 预期结果

下拉列表应该显示：
- 纹理
- 来源
- 物质性
- 性格
- **力学** ← 新增

---

## 🔄 工作流程

### 创建新棱镜后的完整流程

1. **在锚点编辑器中创建棱镜**
   - 访问 http://localhost:5001
   - 创建新棱镜（例如 `mechanics`）
   - 棱镜被添加到 `anchor_config_v2.json`

2. **WebUI自动识别新棱镜**
   - WebUI启动时会调用 `/api/config`
   - 获取最新的棱镜列表
   - 包括新创建的 `mechanics`

3. **在胶囊类型管理中使用**
   - 编辑胶囊类型
   - 在"优先棱镜"下拉列表中可以选择 `mechanics`
   - 保存后，该类型胶囊会默认使用 `mechanics` 棱镜

---

## 🚀 后续优化建议

1. **实时更新**
   - 当创建新棱镜时，通过WebSocket通知WebUI
   - WebUI自动刷新棱镜列表

2. **缓存策略**
   - 缓存棱镜列表，避免频繁请求
   - 设置合理的过期时间

3. **错误处理**
   - 如果API请求失败，显示友好的错误提示
   - 提供重试按钮

4. **多语言支持**
   - 棱镜名称根据用户语言显示
   - 例如：中文用户看到"力学"，英文用户看到"Mechanics"

---

## 📊 相关系统说明

### 系统架构

```
┌─────────────────────────────────────────────────────┐
│  锚点编辑器 (anchor_editor_v2.py)                  │
│  - 管理棱镜配置                                      │
│  - 提供 /api/config API                             │
│  - 配置存储: anchor_config_v2.json                 │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│  WebUI (CapsuleTypeManager.jsx)                    │
│  - 调用 /api/config 获取棱镜列表                     │
│  - 在胶囊类型编辑界面显示棱镜选择器                  │
│  - 动态渲染，支持新增棱镜                            │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│  胶囊API (capsule_api.py)                          │
│  - 接收胶囊类型的 priority_lens 设置                 │
│  - 存储到 capsules.db                              │
└─────────────────────────────────────────────────────┘
```

### 数据关系

- **棱镜**: 分析工具（独立管理）
- **胶囊类型**: 胶囊分类（可选关联优先棱镜）
- **胶囊**: 具体声音胶囊（属于某个胶囊类型）
- **胶囊标签**: 使用某个棱镜分析得到的标签数据

---

## ✅ 修复状态

- [x] 问题诊断
- [x] 代码修改
- [x] 添加动态加载功能
- [x] 添加后备方案
- [ ] 测试验证（需要用户测试）

---

**最后更新**: 2026-01-07
**修复者**: Claude (Sonnet 4.5)
