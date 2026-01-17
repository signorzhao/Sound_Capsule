# Synesth UI 开发技术指南

## 📋 目录

1. [设计系统概述](#设计系统概述)
2. [核心技术栈](#核心技术栈)
3. [设计原则](#设计原则)
4. [色彩系统](#色彩系统)
5. [3D胶囊UI实现](#3d胶囊ui实现)
6. [动画系统](#动画系统)
7. [布局与响应式](#布局与响应式)
8. [组件开发规范](#组件开发规范)
9. [进度条与反馈设计](#进度条与反馈设计)
10. [最佳实践](#最佳实践)

---

## 设计系统概述

Synesth UI 采用**深空科技风格**（Deep Space Tech），结合以下核心特征：

- **深色主题**：黑色背景 (#000) 搭配 zinc 灰度色阶
- **玻璃拟态**：backdrop-blur + 半透明背景
- **3D 质感**：多层 DOM 叠加 + 光影效果
- **动态反馈**：流畅的过渡动画和交互反馈
- **渐变色彩**：每个胶囊类型都有专属的渐变色系

---

## 核心技术栈

### 依赖包

```json
{
  "dependencies": {
    "lucide-react": "^0.294.0",  // 图标库
    "react": "^18.2.0"
  },
  "devDependencies": {
    "tailwindcss": "^3.4.19",           // 核心样式框架
    "tailwindcss-animate": "^1.0.7",   // 动画插件
    "autoprefixer": "^10.4.23",
    "postcss": "^8.5.6"
  }
}
```

### 配置文件

**tailwind.config.js**
```javascript
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // 自定义动画
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
        'twinkle': 'twinkle 8s infinite',
        'slideUp': 'slideUp 0.3s ease',
        'shimmer': 'shimmer 1.5s infinite',
      },
      keyframes: {
        // ... 动画关键帧
      }
    },
  },
  plugins: [
    require('tailwindcss-animate'),
  ],
}
```

---

## 设计原则

### 1. 层次叠加（Layering）

不使用单一 div，而是通过多层绝对定位的 div 叠加实现效果：

```jsx
// ✅ 正确：多层叠加
<div className="relative">
  {/* 背景色 */}
  <div className="absolute inset-0 bg-purple-500"></div>

  {/* 体积阴影层 */}
  <div className="absolute inset-0 bg-gradient-to-r from-black/40 via-transparent to-black/30"></div>

  {/* 高光层 */}
  <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"></div>

  {/* 边缘轮廓光 */}
  <div className="absolute inset-0 border border-white/20"></div>
</div>

// ❌ 错误：单一元素
<div className="bg-purple-500 shadow-lg"></div>
```

### 2. 材质模拟（Material Simulation）

使用透明度叠加模拟不同材质：

- **体积感**：`from-black/40 via-transparent to-black/30`（两侧暗，中间亮）
- **高光反射**：`from-white/80 to-transparent` + `blur-[6px]`
- **轮廓光**：`border-[1px] border-white/20`（在暗背景中勾勒边缘）

### 3. 动画物理（Animation Physics）

使用贝塞尔曲线模拟真实物理运动：

```css
/* 回弹效果 - 胶囊打开动画 */
transition-all duration-700 cubic-bezier(0.34, 1.56, 0.64, 1)

/* 0.34, 1.56, 0.64, 1 的含义：
   - 1.56 > 1：产生"冲过头"效果
   - 模拟机械结构的惯性回弹
*/
```

---

## 色彩系统

### 胶囊类型配色

```javascript
const COLOR_MAP = {
  magic: {
    top: '#8b5cf6',      // purple-500
    bottom: '#c4b5fd',   // purple-300
    name: 'Magic'
  },
  impact: {
    top: '#ef4444',      // red-500
    bottom: '#fca5a5',   // red-300
    name: 'Impact'
  },
  atmosphere: {
    top: '#3b82f6',      // blue-500
    bottom: '#93c5fd',   // blue-300
    name: 'Atmosphere'
  },
  texture: {
    top: '#10b981',      // emerald-500
    bottom: '#6ee7b7',   // emerald-300
    name: 'Texture'
  }
};
```

### 通用色阶

```javascript
// 文字颜色
text-white        // 主标题
text-zinc-300     // 副标题
text-zinc-500     // 辅助信息
text-zinc-600     // 禁用状态

// 背景颜色
bg-black          // 主背景
bg-zinc-900       // 次级背景
bg-zinc-800       // 进度条轨道

// 边框颜色
border-zinc-700   // 组件边框
border-zinc-800   // 分隔线
border-purple-500/30  // 紫色半透明边框
```

---

## 3D胶囊UI实现

### 核心结构

胶囊由**三层**组成，通过 `z-index` 控制层级：

```jsx
<div className="relative w-40 h-80" style={{ perspective: '1000px' }}>

  {/* 1. The Cap (上半部分) - z-30 - 最上层 */}
  <div className="absolute top-0 w-full h-[52%] rounded-t-full z-30"
       style={{
         transform: isOpen ? 'translateY(-70px) rotate(-5deg)' : 'translateY(0)',
         transformOrigin: '50% 100%'
       }}>
    {/* 材质叠加层 */}
  </div>

  {/* 2. The Core (内部机械) - z-20 - 中间层 */}
  <div className="absolute top-[30%] bottom-[30%] z-20 flex items-center justify-center">
    {/* 连接杆 */}
    <div className="w-2 h-[140%] bg-zinc-800 absolute"></div>
    {/* 按钮 */}
    <div className="bg-black border border-zinc-700 px-6 py-3 rounded-xl">
      {/* 按钮内容 */}
    </div>
  </div>

  {/* 3. The Body (下半部分) - z-10 - 最底层 */}
  <div className="absolute bottom-0 w-[92%] h-[50%] rounded-b-full z-10"
       style={{
         transform: isOpen ? 'translateY(70px) rotate(5deg)' : 'translateY(0)',
         transformOrigin: '50% 0%'
       }}>
    {/* 材质叠加层 */}
  </div>

</div>
```

### 材质层叠加详解

#### 1. 体积阴影（Volume Shadow）

```jsx
<div className="absolute inset-0 bg-gradient-to-r from-black/40 via-transparent to-black/30 pointer-events-none"></div>
```

**作用**：让圆柱体两侧变暗，中间变亮，产生体积感

#### 2. 高光层（Specular Highlight）

```jsx
<div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent opacity-50 pointer-events-none"
     style={{ backgroundSize: '200% 100%', backgroundPosition: '30% 0' }}>
</div>
```

**作用**：模拟光线打在光滑塑料表面的反射

#### 3. 轮廓光（Rim Light）

```jsx
<div className="absolute inset-0 rounded-t-full border-[1px] border-white/20 pointer-events-none"></div>
<div className="absolute top-10 right-3 w-[1px] h-[60%] bg-white/60 blur-[2px]"></div>
```

**作用**：在黑色背景中勾勒出胶囊的边缘

#### 4. 强高光点（Specular Point）

```jsx
<div className="absolute top-6 left-5 w-[30%] h-[40%] bg-gradient-to-b from-white/80 to-transparent rounded-full blur-[6px]"></div>
```

**作用**：模拟顶部强光源照射形成的高光点

### 打开/关闭动画

```jsx
// 使用 Tailwind 类名 + style 实现
<div
  className={`absolute ... transition-all duration-700 ${
    isOpen ? 'translate-y-[-70px] -rotate-5' : ''
  }`}
  style={{
    backgroundColor: colorTop,
    transformOrigin: '50% 100%',
    boxShadow: isOpen
      ? '0 25px 35px -5px rgba(0,0,0,0.8), inset 0 -2px 5px rgba(0,0,0,0.5)'
      : '0 4px 15px rgba(0,0,0,0.8)'
  }}
>
```

**关键点**：
- `duration-700`：足够长的动画时间让用户看清细节
- `translate-y-[-70px] -rotate-5`：向上移动并旋转 -5 度
- `inset 0 -2px 5px`：打开时添加内部阴影，模拟厚度

---

## 动画系统

### 自定义动画

在 `tailwind.config.js` 中定义：

```javascript
animation: {
  'twinkle': 'twinkle 8s infinite',     // 星空闪烁
  'shimmer': 'shimmer 1.5s infinite',   // 进度条闪光
  'slideUp': 'slideUp 0.3s ease',       // 上滑进入
  'float': 'float 6s ease-in-out infinite',  // 悬浮
},
keyframes: {
  twinkle: {
    '0%, 100%': { opacity: '0.3' },
    '50%': { opacity: '0.5' },
  },
  shimmer: {
    '0%': { transform: 'translateX(-100%)' },
    '100%': { transform: 'translateX(100%)' },
  },
  slideUp: {
    'from': { opacity: '0', transform: 'translateY(10px)' },
    'to': { opacity: '1', transform: 'translateY(0)' },
  },
  float: {
    '0%, 100%': { transform: 'translateY(0px)' },
    '50%': { transform: 'translateY(-10px)' },
  }
}
```

### 使用动画

```jsx
{/* 方法1：使用预定义动画 */}
<div className="animate-spin"></div>
<div className="animate-pulse"></div>

{/* 方法2：使用自定义动画 */}
<div className="animate-[shimmer_1.5s_infinite]"></div>

{/* 方法3：使用 inline style */}
<div style={{ animation: 'twinkle 8s infinite' }}></div>
```

### 动画延迟

```jsx
{/* 多个元素依次出现 */}
{[0, 1, 2].map((i) => (
  <div
    key={i}
    className="animate-pulse"
    style={{ animationDelay: `${i * 0.15}s` }}
  />
))}
```

---

## 布局与响应式

### 网格布局

```jsx
{/* 胶囊网格：响应式列数 */}
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-16 justify-items-center items-center">
  {capsules.map(capsule => (
    <CapsuleCard key={capsule.id} capsule={capsule} />
  ))}
</div>

{/* 说明：
  - 移动端：1列
  - 平板（md）：2列
  - 桌面（lg）：3列
  - gap-16：胶囊之间的间距
  - justify-items-center：水平居中
  - items-center：垂直居中
*/}
```

### Flexbox 布局

```jsx
{/* 水平居中，两端对齐 */}
<div className="flex items-center justify-between gap-4">
  <div>左侧</div>
  <div className="flex-1 text-center">中间</div>
  <div className="flex justify-end">右侧</div>
</div>

{/* 垂直居中 */}
<div className="flex items-center justify-center min-h-screen">
  内容
</div>
```

### 固定定位

```jsx
{/* 固定在底部 */}
<div className="fixed bottom-0 left-0 right-0 z-50">
  内容
</div>

{/* 固定在顶部 */}
<div className="sticky top-0 z-50 backdrop-blur-xl">
  顶部导航
</div>
```

---

## 组件开发规范

### 1. 组件结构

```jsx
import React from 'react';
import { IconName } from 'lucide-react';

/**
 * 组件描述
 *
 * @param {Object} props - 组件属性
 * @param {string} props.title - 标题
 * @param {Function} props.onClick - 点击回调
 */
const ComponentName = ({ title, onClick }) => {
  // 1. 状态管理
  const [isOpen, setIsOpen] = useState(false);

  // 2. 计算值
  const bgColor = isOpen ? 'bg-white' : 'bg-black';

  // 3. 事件处理
  const handleClick = () => {
    setIsOpen(!isOpen);
    onClick?.();
  };

  // 4. 渲染
  return (
    <div className={bgColor} onClick={handleClick}>
      {title}
    </div>
  );
};

export default ComponentName;
```

### 2. 样式组织

```jsx
// ✅ 推荐：使用 Tailwind 类名
<div className="relative w-40 h-80 bg-black rounded-2xl shadow-lg">

// ❌ 避免：使用 CSS 文件
<div className="custom-card">

// ✅ 推荐：动态样式使用 style
<div style={{ backgroundColor: dynamicColor, transform: `scale(${scale})` }}>

// ❌ 避免：复杂的内联样式
<div style={{
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center'
}}>
```

### 3. 图标使用

```jsx
import { Sparkles, Flame, Zap, Wind, Music } from 'lucide-react';

// 图标映射
const ICON_MAP = {
  magic: Sparkles,
  impact: Flame,
  atmosphere: Wind,
  texture: Music
};

// 使用
const Icon = ICON_MAP[type] || Sparkles;
<Icon size={20} className="text-purple-500" />
```

### 4. 条件渲染

```jsx
// ✅ 推荐：使用逻辑与 &&
{isOpen && <div>内容</div>}

// ✅ 推荐：使用三元运算符
<div className={isOpen ? 'bg-white' : 'bg-black'}>

// ✅ 推荐：使用 clsx 或类名字符串拼接
<div className={`base-class ${isActive ? 'active' : 'inactive'}`}>

// ❌ 避免：使用复杂的三元嵌套
<div className={condition1 ? (condition2 ? 'a' : 'b') : 'c'}>
```

---

## 进度条与反馈设计

### 进度条实现

```jsx
<div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
  <div
    className="h-full rounded-full transition-all duration-300 relative overflow-hidden"
    style={{
      width: `${progress}%`,
      background: `linear-gradient(to right, ${colorTop}, ${colorBottom})`
    }}
  >
    {/* 闪光动画 */}
    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-[shimmer_1.5s_infinite]"></div>
  </div>
</div>
```

**关键点**：
- `overflow-hidden`：确保进度条不超出圆角
- `transition-all duration-300`：平滑过渡
- `relative` + `absolute`：叠加闪光层

### 底部固定横幅

```jsx
<div className="fixed bottom-0 left-0 right-0 z-50 bg-black/90 backdrop-blur-xl border-t border-zinc-800">
  <div className="max-w-7xl mx-auto px-6 py-4">
    {/* 内容 */}
  </div>
</div>
```

**关键点**：
- `fixed bottom-0 left-0 right-0`：固定在底部
- `bg-black/90`：90% 不透明度
- `backdrop-blur-xl`：毛玻璃效果
- `border-t`：顶部边框分隔

### 加载动画

```jsx
{/* 旋转加载圈 */}
<div className="relative w-12 h-12">
  <div className="absolute inset-0 rounded-full border-2 border-zinc-700"></div>
  <div
    className="absolute inset-0 rounded-full border-2 border-transparent border-t-purple-500 animate-spin"
    style={{ borderTopColor: dynamicColor }}
  ></div>
  <div className="absolute inset-0 flex items-center justify-center">
    <Icon size={16} style={{ color: dynamicColor }} />
  </div>
</div>
```

### 成功提示

```jsx
<div className="fixed bottom-0 left-0 right-0 z-50 bg-black/90 backdrop-blur-xl border-t border-zinc-800">
  <div className="max-w-7xl mx-auto px-6 py-4">
    <div className="flex items-center gap-4">
      {/* 图标 */}
      <div className="relative w-12 h-12 flex-shrink-0">
        <div className="absolute inset-0 rounded-full bg-gradient-to-br from-purple-500/20 to-pink-500/20 blur-sm"></div>
        <div className="absolute inset-0 rounded-full border border-purple-500/30 flex items-center justify-center">
          <CheckIcon className="w-6 h-6 text-purple-400" />
        </div>
      </div>

      {/* 文字 */}
      <div className="flex-1">
        <h3 className="text-sm font-bold tracking-wide text-white uppercase">Capsule Saved</h3>
        <p className="text-xs text-zinc-500 tracking-wider mt-0.5">Redirecting...</p>
      </div>

      {/* 进度指示器 */}
      <div className="flex gap-1.5">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-zinc-600 animate-pulse"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
    </div>
  </div>
</div>
```

---

## 最佳实践

### 1. 性能优化

```jsx
// ✅ 使用 CSS 变换代替位置变化
<div className="transition-transform duration-300 hover:scale-105">

// ❌ 避免改变 top/left
<div style={{ top: isOpen ? '-70px' : '0' }}>

// ✅ 使用 opacity 和 transform 做动画
<div className="transition-all duration-500 opacity-0 scale-75">

// ✅ 使用 will-change 提示浏览器
<div className="will-change-transform">
```

### 2. 可访问性

```jsx
// ✅ 使用语义化标签
<button className="...">点击</button>

// ✅ 添加 aria-label
<button aria-label="关闭对话框">
  <XIcon />
</button>

// ✅ 键盘导航
<div tabIndex={0} role="button" onKeyDown={(e) => e.key === 'Enter' && onClick()}>
```

### 3. 响应式图片

```jsx
// ✅ 使用合适的图片尺寸
<img
  srcSet="small.jpg 320w, medium.jpg 640w, large.jpg 1280w"
  sizes="(max-width: 640px) 320px, (max-width: 1280px) 640px, 1280px"
  src="medium.jpg"
  alt="描述"
/>
```

### 4. 深色模式

```jsx
// 我们的系统默认深色模式，所以：
// ✅ 使用深色基础色
bg-black, bg-zinc-900, text-white

// ✅ 使用半透明叠加
bg-white/10, bg-black/50

// ✅ 使用 zinc 色阶代替 gray
text-zinc-300, border-zinc-700
```

### 5. 渐变使用

```jsx
// ✅ 线性渐变
bg-gradient-to-r from-purple-500 to-pink-500

// ✅ 径向渐变
bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))]

// ✅ 使用透明度
from-purple-500/80 to-transparent

// ✅ 背景渐变叠加
<div className="bg-gradient-to-br from-indigo-900/20 to-blue-900/20">
```

---

## 常用代码片段

### 玻璃拟态卡片

```jsx
<div className="bg-black/80 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
  内容
</div>
```

### 发光按钮

```jsx
<button className="bg-purple-500 hover:bg-purple-600 text-white font-semibold px-6 py-3 rounded-xl shadow-lg hover:shadow-purple-500/50 transition-all hover:-translate-y-0.5">
  点击
</button>
```

### 背景装饰

```jsx
<div className="absolute inset-0 pointer-events-none">
  <div className="absolute top-[-10%] left-[20%] w-[800px] h-[800px] bg-indigo-900/10 blur-[120px] rounded-full"></div>
  <div className="absolute bottom-[-10%] right-[10%] w-[600px] h-[600px] bg-blue-900/10 blur-[100px] rounded-full"></div>
</div>
```

### 星空背景

```jsx
<div className="fixed inset-0 bg-[radial-gradient(2px_2px_at_20px_30px,#eee,rgba(0,0,0,0)),radial-gradient(2px_2px_at_40px_70px,#fff,rgba(0,0,0,0)),radial-gradient(2px_2px_at_50px_160px,#ddd,rgba(0,0,0,0)),radial-gradient(2px_2px_at_90px_40px,#fff,rgba(0,0,0,0)),radial-gradient(2px_2px_at_130px_80px,#fff,rgba(0,0,0,0))] bg-[length:200px_200px] animate-[twinkle_8s_infinite] opacity-30"></div>
```

---

## 调试技巧

### 1. 检查 Tailwind 是否工作

```jsx
// 使用极端颜色测试
<div className="bg-red-600 border-4 border-blue-600 text-4xl font-bold">
  TAILWIND 测试
</div>
```

### 2. 检查层级（z-index）

```jsx
// 使用不同颜色标识层级
<div className="z-10 bg-red-500">z-10</div>
<div className="z-20 bg-blue-500">z-20</div>
<div className="z-30 bg-green-500">z-30</div>
```

### 3. 检查动画

```jsx
// 使用明显的动画测试
<div className="animate-spin w-20 h-20 bg-purple-500">
  旋转测试
</div>
```

---

## 参考资源

### 官方文档
- [Tailwind CSS](https://tailwindcss.com/docs)
- [Lucide Icons](https://lucide.dev/icons/)
- [React](https://react.dev/)

### 设计灵感
- 胶囊UI设计实现指南.md - 本项目的3D胶囊设计详解
- capsule vault source.html - 原型参考代码

### 工具
- [Tailwind CSS Color Palette](https://uicolors.app/) - 配色工具
- [Cubic Bezier](https://cubic-bezier.com/) - 贝塞尔曲线可视化

---

## 更新日志

### 2026-01-05
- ✅ 初始版本
- ✅ 完成3D胶囊UI实现
- ✅ 完成进度条和反馈设计
- ✅ 完成SaveCapsuleHome组件重构

---

**文档版本**: v1.0.0
**最后更新**: 2026-01-05
**维护者**: Synesth 开发团队
