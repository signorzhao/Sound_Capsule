# 🎛️ Project Synesth / SoundMap v2.0
>
> **AI 语义力场驱动的声音形容词探索工具**

**Project Synesth** 是一款专为声音设计师和游戏音频专家打造的直觉式辅助工具。它将抽象的感性描述转化为直观的几何空间，通过 AI 语义向量技术实现声音关键词的精准导航。

[系统架构说明](file:///Users/ianzhao/Documents/pluginpresetslist/Project%20Synesth/docs/ARCHITECTURE.md) | [开发与部署指南](file:///Users/ianzhao/Documents/pluginpresetslist/Project%20Synesth/docs/DEVELOPMENT.md)

---

## 💎 核心系统架构

### 1. 语义引力场引擎 (Force Field Engine)

系统通过多维向量模型将每一个词库词汇投射到由用户定义的**锚点 (Anchors)** 空间中。

> [!IMPORTANT]
> **算法核心：多点反距离加权 (IDW) 变体**
> 我们采用了基于余弦相似度的指数加权公式：$Weight = \max(0, \cos(\theta))^8$。
>
> - **语义拉引**：词汇点会像受到磁铁吸引一样，根据语义契合度向各个锚点移动。
> - **8次方偏置**：通过高阶指数，我们极大地增强了锚点的“排他性”，使得词汇能更清晰地向特定的语义重心靠拢，减少模糊区域。

### 2. 空间平滑变换 (Tie-Aware Smooth Stretch)

为了解决大量词汇在语义空间中重叠的问题，v2.0 引入了智能空间分层：

- **并列处理**：专门针对语义完全一致或极度相似（Ties）的情况进行平均排名优化，防止点位在视觉上出现重叠。
- **动态拉伸**：利用 `scipy.stats.rankdata` 实现非线性的空间均匀化分布，确保整个画布的利用率达到最高。

### 3. 智能词性驱动系统 (Word-Type Filtering)

基于 `NLP` 语义分类器，系统将总库词汇自动划分为三类，用户可以根据当前透镜的语义目标动态开启过滤：

| 类别 | 描述 | 适用透镜示例 |
| :--- | :--- | :--- |
| **形容词 (Adjectives)** | 抽象质感、情绪特征 | 质感 (Texture) / 性情 (Temperament) |
| **名词 (Nouns)** | 物理实体、场所、材质 | 材质 (Materiality) / 空间 (Space) |
| **动词 (Verbs)** | 动态动作、物理过程 | 源场 (Source) & 物理动态 |

---

## 🔍 透镜系统 (Lenses) 深度解析

| 透镜名称 | 语义重心 (Axes & Anchors) | 分类过滤策略 | 交互目标 |
| :--- | :--- | :--- | :--- |
| **质感 (Texture)** | 光明/黑暗，数字/模拟，有机/人工 | 仅形容词 | 寻找音色的“颗粒感”与“色彩” |
| **材质 (Materiality)** | 贴耳/遥远，封闭/开阔，石质/金属 | 聚焦名词 | 定位声音发生的“物理空间” |
| **源场 (Source)** | 静态持叙/瞬时冲击，柔和/暴力 | 名词 + 动词 | 定义声音产生的“物理动作” |
| **性情 (Temperament)** | 平静/躁动，简洁/复杂 | 仅形容词 | 赋予声音独特的人格属性 |

---

## 🛠️ 维护与扩展

### 数据流水线 (Data Pipeline)

1. **自动分类**：运行 `smart_categorize_v2.py`，它会利用多语言 MiniLM 模型自动更新词库标签。
2. **可视化重构**：
   - 启动后端 `anchor_editor_v2.py`。
   - 访问 `http://localhost:5001`，通过 **可视化界面** 拖拽锚点。
   - 点击 **“保存并重构”**，系统将通过 SSE (Server-Sent Events) 实时推送计算进度。

### 词库扩展

只需在 `master_lexicon_v3.csv` 中添加 `word_cn, word_en`，系统将在下一次重构时自动完成语义映射。

---

## 🚀 启动指引

### 数据编辑端 (后端/编辑器)

```bash
cd data-pipeline
python anchor_editor_v2.py
```

### 用户预览端 (前端/客户端)

```bash
cd webapp
npm run dev
```

---
> [!TIP]
> **设计哲学**：Project Synesth 试图填补“技术参数”与“感性直觉”之间的鸿沟。让词汇不再是枯燥的列表，而是一个可以随心漫游的声学风景。

Made with ❤️ for the future of Sound Design.
