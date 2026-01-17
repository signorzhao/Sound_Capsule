以下是详细的分析和优化建议：

### 1. 🔍 现状审计与去重 (Gap Analysis)

您在 **Phase B** 中已经完成了大量底层设施，这份新计划中的部分任务实际上已经是 **Done** 或 **Partial** 状态。

|**JIT 计划中的任务 ID**|**任务描述**|**现状分析 (基于 Phase B1-B4 报告)**|**建议操作**|
|---|---|---|---|
|`db-migration`|添加 `file_download_status`|**⚠️ 重复/冲突**<br><br>  <br><br>Phase B1 已经添加了 `asset_status` 字段。|**跳过新建**。直接复用 `asset_status` 字段 (值为 `cloud_only`, `partial`, `synced`)。|
|`backend-task-manager`|实现 `DownloadTask` 和队列|**✅ 已完成**<br><br>  <br><br>Phase B2 报告显示 `DownloadQueue` 和 `ResumableDownloader` 已实现。|**复用**。直接调用现有的 `download_manager.py`，不要重写。|
|`backend-download-api`|完善下载 API|**🔄 需要调整**<br><br>  <br><br>Phase B4 实现了 `lightweight` 同步。这里需要暴露一个显式的 `POST /download-assets` 接口来触发 B2 的队列。|**修改**。基于现有的 `DownloadQueue` 封装一个启动下载的 API。|
|`tauri-commands`|`open_rpp_in_reaper`|**🆕 新增**<br><br>  <br><br>之前只实现了 Python 调用 REAPER，现在需要前端通过 Tauri 直接触发（或通过 Python 触发）。|**执行**。这是本次的核心集成点。|
|`frontend-integration`|重构 `handleImportToReaper`|**🆕 新增**<br><br>  <br><br>这是 JIT 逻辑的核心。|**重点执行**。|

---

### 💡 2. 优化后的 JIT 执行逻辑

基于上述分析，我为您优化了执行路径，**省去了约 40% 的后端重复开发工作**。

#### 核心状态机 (State Machine)

利用 Phase B1 现有的 `asset_status`：

- **`cloud_only` (☁️)**: 只有元数据。 -> **触发 JIT 弹窗**
    
- **`downloading` (🔄)**: 正在下载。 -> **显示进度环 / 暂停**
    
- **`synced` (✅)**: 完整资产。 -> **直接打开 REAPER**
    
- **`partial` (⚠️)**: 下载中断/不完整。 -> **触发 JIT 弹窗 (提示修复)**
    

### 🛠️ 3. 修正后的实施步骤

请按照以下简化后的步骤执行：

#### **Step 1: 后端接口对接 (Python)**

_不需要重写下载器，只需要连接它。_

- **修改 `capsule_api.py`**:
    
    - 确认 `POST /api/capsules/<id>/download_assets` 接口存在。
        
    - 该接口应调用 `download_manager.add_task(capsule_id)` (复用 Phase B2)。
        
    - 确认 `GET /api/downloads/status` 能返回进度 (复用 Phase B2)。
        

#### **Step 2: 前端组件开发 (React)**

这是工作量最大的部分。

1. **创建 `DownloadConfirmModal.jsx` (JIT 决策框)**
    
    - **UI**: 显示 "下载并打开" (高亮) 和 "仅打开工程" (幽灵按钮)。
        
    - **Pro Tip**: 如果选择"仅打开"，提示用户"媒体文件将离线"。
        
2. **创建 `SmartActionButton.jsx` (智能按钮)**
    
    - **逻辑**: 这是一个纯 UI 组件，根据 `status` 渲染不同图标（云朵、加载圈、REAPER Logo）。
        
    - **解耦**: 不要把业务逻辑写在里面，只通过 `onClick` 抛出事件。
        

#### **Step 3: 逻辑集成 (The "Brain")**

在 `CapsuleLibrary.jsx` 中重构点击处理函数：

JavaScript

```
const handleSmartClick = async (capsule) => {
  const status = capsule.asset_status; // 使用数据库中的字段

  // 1. 已经就绪 -> 直接打开
  if (status === 'synced') {
    await openInReaper(capsule.id);
    return;
  }

  // 2. 正在下载 -> 暂停或显示详情
  if (status === 'downloading') {
    showDownloadDetails(capsule.id);
    return;
  }

  // 3. 未下载/不完整 -> JIT 决策
  // 弹出 Modal，用户选择后返回 result
  const choice = await DownloadConfirmModal.show({
    title: "资产未就绪",
    size: capsule.local_wav_size || "未知大小"
  });

  if (choice === 'download_and_open') {
    // A. 触发后端下载队列
    await api.post(`/capsules/${capsule.id}/download_assets`);
    // B. 开启轮询检查进度
    startPollingProgress(capsule.id, () => openInReaper(capsule.id));
  } else if (choice === 'open_rpp_only') {
    // C. 仅打开 RPP (离线模式)
    await openInReaper(capsule.id, { offline: true });
  }
};
```