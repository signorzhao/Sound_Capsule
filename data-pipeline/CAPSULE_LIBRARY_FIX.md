# 胶囊库标签显示修复

**日期**: 2026-01-07
**问题**: 在胶囊库列表中，新建棱镜（如 mechanics）的标签不会显示

---

## 🔍 问题原因

在 `CapsuleLibrary.jsx` 中，有两个硬编码的映射对象：

### 1. 棱镜名称映射 (lensNames)
```jsx
const lensNames = {
  texture: '质感',
  source: '源场',
  materiality: '材质',
  temperament: '气质'
  // 缺少 mechanics!
};
```

### 2. 棱镜颜色映射 (lensColors)
```jsx
const lensColors = {
  texture: 'text-purple-400 bg-purple-900/20 border-purple-900/30',
  source: 'text-orange-400 bg-orange-900/20 border-orange-900/30',
  materiality: 'text-teal-400 bg-teal-900/20 border-teal-900/30',
  temperament: 'text-pink-400 bg-pink-900/20 border-pink-900/30'
  // 缺少 mechanics!
};
```

### 问题影响

当胶囊有新棱镜（如 `mechanics`）的标签时：
- ✅ 标签数据会被加载（第688行遍历 `safeTags` 时会找到）
- ❌ 但没有对应的名称和颜色配置
- ❌ 标签会使用默认的灰色 (`text-zinc-400`)
- ❌ 棱镜名称无法显示

---

## ✅ 解决方案

添加 `mechanics` 棱镜到映射对象中：

```jsx
const lensNames = {
  texture: '质感',
  source: '源场',
  materiality: '材质',
  temperament: '气质',
  mechanics: '力学'  // 新增
};

const lensColors = {
  texture: 'text-purple-400 bg-purple-900/20 border-purple-900/30',
  source: 'text-orange-400 bg-orange-900/20 border-orange-900/30',
  materiality: 'text-teal-400 bg-teal-900/20 border-teal-900/30',
  temperament: 'text-pink-400 bg-pink-900/20 border-pink-900/30',
  mechanics: 'text-emerald-400 bg-emerald-900/20 border-emerald-900/30'  // 新增（绿色）
};
```

---

## 📋 修改的文件

**文件**: `webapp/src/components/CapsuleLibrary.jsx`

**修改位置**:
- 第594-600行：添加 `mechanics: '力学'` 到 `lensNames`
- 第603-609行：添加 `mechanics` 颜色配置到 `lensColors`

---

## 🎯 颜色方案

为5个棱镜选择了不同的颜色，便于视觉区分：

| 棱镜 | 中文名称 | 颜色 | Tailwind 类 |
|------|---------|------|-------------|
| texture | 质感 | 紫色 | `text-purple-400 bg-purple-900/20` |
| source | 源场 | 橙色 | `text-orange-400 bg-orange-900/20` |
| materiality | 材质 | 青色 | `text-teal-400 bg-teal-900/20` |
| temperament | 气质 | 粉色 | `text-pink-400 bg-pink-900/20` |
| mechanics | 力学 | 绿色 | `text-emerald-400 bg-emerald-900/20` |

---

## 🧪 测试验证

### 验证步骤

1. **准备测试数据**
   - 确保数据库中有胶囊
   - 确保某个胶囊有 `mechanics` 棱镜的标签

2. **查看胶囊库**
   - 打开WebUI
   - 进入胶囊库
   - 查看胶囊卡片

3. **检查标签显示**
   - 应该能看到所有棱镜的标签
   - mechanics 标签应该是绿色
   - 鼠标悬停应该能看到棱镜名称

### 预期结果

```
胶囊卡片示例:
┌────────────────────────────────────┐
│ MAGIC_001                           │
│ ────────────────────────────────── │
│ 标签:                               │
│ [质感] Bright                      │ ← 紫色
│ [源场] Synth                        │ ← 橙色
│ [力学] Heavy                        │ ← 绿色 (新增)
│ [气质] Calm                         │ ← 粉色
└────────────────────────────────────┘
```

---

## 🔄 代码逻辑说明

### 标签显示流程

1. **加载标签数据**
   ```jsx
   const tags = tagsCache[capsule.id];
   // tags = { texture: [...], source: [...], mechanics: [...] }
   ```

2. **遍历每个棱镜的标签**
   ```jsx
   Object.entries(safeTags).map(([lens, lensTags]) => {
     // lens = 'mechanics'
     // lensTags = [{word_cn: '沉重', ...}, ...]
   ```

3. **获取颜色配置**
   ```jsx
   const lensColorClass = lensColors[lens] || 'text-zinc-400';
   // lensColors['mechanics'] = 'text-emerald-400 bg-emerald-900/20 ...'
   ```

4. **提取文本颜色**
   ```jsx
   const textColorClass = lensColorClass.split(' ')[0];
   // textColorClass = 'text-emerald-400'
   ```

5. **渲染标签**
   ```jsx
   <span className={`... ${textColorClass}`}>
     {tagText}
   </span>
   // 绿色的"沉重"
   ```

### 兜底机制

如果未来添加新棱镜而忘记更新映射：
- `lensColors[lens]` 会返回 `undefined`
- 使用默认值 `|| 'text-zinc-400'`
- 标签会显示为灰色，不会出错

---

## 🚀 后续优化建议

### 1. 动态加载棱镜配置

与其在每个组件中维护映射对象，不如从API动态加载：

```jsx
const [lensConfig, setLensConfig] = useState({});

useEffect(() => {
  fetch('http://localhost:5001/api/config')
    .then(res => res.json())
    .then(config => {
      const lensConfig = {};
      Object.keys(config).forEach(lensId => {
        lensConfig[lensId] = {
          name: config[lensId].name,
          // 根据名称或配置生成颜色
          color: generateColorForLens(lensId)
        };
      });
      setLensConfig(lensConfig);
    });
}, []);
```

### 2. 统一的棱镜配置管理

创建一个统一的棱镜配置模块：

```jsx
// utils/lensConfig.js
export const useLensConfig = () => {
  const [config, setConfig] = useState({});

  useEffect(() => {
    // 从API加载
  }, []);

  return {
    getLensName: (lensId) => config[lensId]?.name || lensId,
    getLensColor: (lensId) => config[lensId]?.color || 'text-zinc-400',
    getAllLenses: () => Object.keys(config)
  };
};
```

### 3. 自动颜色生成

使用哈希算法根据棱镜ID自动生成颜色：

```jsx
function generateColorForLens(lensId) {
  const colors = [
    'purple', 'orange', 'teal', 'pink', 'emerald',
    'blue', 'rose', 'cyan', 'indigo', 'violet'
  ];
  const hash = lensId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return colors[hash % colors.length];
}
```

---

## 📊 相关文件修改总结

今天修改的所有文件：

1. **anchor_generator.py** - 添加词性过滤和去重功能
2. **anchor_editor_v2.py** - 添加词性选择UI、自动创建CSV
3. **CapsuleTypeManager.jsx** - 动态加载棱镜列表
4. **CapsuleLibrary.jsx** - 添加 mechanics 棱镜名称和颜色（本次修改）
5. **lexicon_mechanics.csv** - 补充词汇数据

---

## ✅ 修复状态

- [x] 问题诊断
- [x] 添加 mechanics 名称映射
- [x] 添加 mechanics 颜色映射
- [x] 代码修改完成
- [ ] 用户测试验证

---

**最后更新**: 2026-01-07
**修复者**: Claude (Sonnet 4.5)
