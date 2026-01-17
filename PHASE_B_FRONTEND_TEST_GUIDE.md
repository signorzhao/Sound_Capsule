# Phase B: 文件云存储 - 前端测试指南

**日期**: 2026-01-11
**状态**: ✅ 后端完成，待前端测试
**版本**: v1.0

---

## 📋 测试目标

在 Web UI 中完整测试胶囊的上传和下载流程，包括：
1. ✅ 上传胶囊元数据到云端
2. ✅ 上传胶囊文件（预览音频 + RPP + Audio 文件夹）
3. ✅ 查看云端同步状态
4. ✅ 从云端下载完整胶囊
5. ✅ 在 REAPER 中打开下载的项目

---

## 🔧 前置条件

### 1. 确保 API 服务器正在运行

```bash
cd data-pipeline
./venv/bin/python capsule_api.py > api.log 2>&1 &
```

检查状态：
```bash
curl http://localhost:5002/api/health
```

应该返回：
```json
{"status": "ok"}
```

### 2. 确保 Web 应用已启动

```bash
cd webapp
npm run tauri dev
```

### 3. 确保已登录

- 打开应用后，确保已经以 `ianz` 用户登录
- 如果没有登录，请先登录

---

## 🧪 测试步骤

### 测试 1: 查看现有胶囊的云同步状态

**步骤**：
1. 打开 Web 应用
2. 进入"胶囊库"页面
3. 查看胶囊列表
4. 检查每个胶囊的状态标识

**预期结果**：
- 胶囊 141 (magic_ianzhao_20260110_182907) 应该显示 `cloud_status='synced'`
- 其他胶囊可能显示 `cloud_status='local'`

**SQL 验证**：
```bash
sqlite3 data-pipeline/database/capsules.db \
  "SELECT id, name, cloud_status, cloud_id, cloud_version FROM capsules WHERE id = 141"
```

预期输出：
```
141|magic_ianzhao_20260110_182907|synced|9d10d75a-dcbd-47bd-8464-1cf8b23b4092|2
```

---

### 测试 2: 上传新胶囊到云端

**步骤**：
1. 选择一个**未同步**的胶囊（`cloud_status='local'`）
2. 点击"同步到云端"按钮
3. 观察上传进度和状态变化

**示例操作**：
1. 找到胶囊 ID 142（或其他 local 状态的胶囊）
2. 点击"上传"或"同步"按钮
3. 等待上传完成

**预期结果**：
- ✅ 前端显示上传成功提示
- ✅ 胶囊状态变为 `synced`
- ✅ 显示云端版本号

**API 请求示例**：
```javascript
// 通过浏览器控制台测试
fetch('http://localhost:5002/api/sync/upload', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    table_name: 'capsules'
  })
})
.then(r => r.json())
.then(data => console.log(data))
```

预期响应：
```json
{
  "success": true,
  "data": {
    "uploaded": 1,
    "failed": 0
  }
}
```

**验证云端数据**：
```bash
cd data-pipeline
./venv/bin/python -c "
from supabase_client import get_supabase_client
supabase = get_supabase_client()
capsules = supabase.download_capsules('f4451f95-8b6a-4647-871a-c30b9ad2eb7b')
print(f'云端胶囊数: {len(capsules)}')
for cap in capsules:
    print(f\"  - {cap['name']} (本地ID: {cap['local_id']}, 版本: {cap['version']})\")
"
```

---

### 测试 3: 查看云端文件状态

**步骤**：
1. 打开浏览器开发者工具（F12）
2. 在 Console 中执行以下代码：

```javascript
// 检查胶囊 141 的云端文件
const capsuleId = 141;

fetch(`http://localhost:5002/api/capsules/${capsuleId}`)
  .then(r => r.json())
  .then(data => {
    console.log('胶囊信息:', data.capsule);
    console.log('云同步状态:', data.capsule.cloud_status);
    console.log('云端 ID:', data.capsule.cloud_id);
    console.log('云端版本:', data.capsule.cloud_version);
  });
```

**预期输出**：
```javascript
{
  id: 141,
  name: "magic_ianzhao_20260110_182907",
  cloud_status: "synced",
  cloud_id: "9d10d75a-dcbd-47bd-8464-1cf8b23b4092",
  cloud_version: 2,
  // ... 其他字段
}
```

---

### 测试 4: 模拟从云端下载胶囊

**注意**：当前可能还没有前端下载按钮，需要通过 API 测试。

**API 测试**：

创建一个临时测试脚本：

```bash
cd data-pipeline
cat > test_frontend_download.py << 'EOF'
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '.')

from capsule_db import CapsuleDatabase
from supabase_client import get_supabase_client

# 1. 从云端下载元数据
supabase = get_supabase_client()
user_id = 'f4451f95-8b6a-4647-871a-c30b9ad2eb7b'

print("从云端下载胶囊列表...")
cloud_capsules = supabase.download_capsules(user_id)
print(f"✓ 云端有 {len(cloud_capsules)} 个胶囊")

# 2. 找到胶囊 141
capsule_141 = next((c for c in cloud_capsules if c['local_id'] == 141), None)
if capsule_141:
    print(f"\n✓ 找到胶囊 141:")
    print(f"  名称: {capsule_141['name']}")
    print(f"  版本: {capsule_141['version']}")
    print(f"  云端ID: {capsule_141['id']}")

    # 3. 下载文件
    print("\n下载文件到本地...")
    from pathlib import Path

    test_dir = Path('output/test_frontend_download')
    test_dir.mkdir(parents=True, exist_ok=True)

    # 下载 RPP
    supabase.download_file(user_id, 141, 'rpp', str(test_dir / 'test.rpp'))

    # 下载预览
    supabase.download_file(user_id, 141, 'preview', str(test_dir / 'test_preview.ogg'))

    # 下载 Audio 文件夹
    supabase.download_file(user_id, 141, 'audio_folder', str(test_dir))

    print(f"\n✓ 下载完成，文件保存在: {test_dir.absolute()}")
EOF

./venv/bin/python test_frontend_download.py
```

**预期结果**：
```
从云端下载胶囊列表...
✓ 云端有 X 个胶囊

✓ 找到胶囊 141:
  名称: magic_ianzhao_20260110_182907
  版本: 2
  云端ID: 9d10d75a-dcbd-47bd-8464-1cf8b23b4092

下载文件到本地...
✓ 下载文件成功: f4451f95-8b6a-4647-871a-c30b9ad2eb7b/141/project.rpp
✓ 下载文件成功: f4451f95-8b6a-4647-871a-c30b9ad2eb7b/141/preview.ogg
  ✓ Bell,Pepper,Crunch,Crack,Break02.wav (827,434 bytes)
  ... (8 个音频文件)

✓ Audio 文件夹下载完成:
  成功: 8 个文件
  总大小: 32,166,666 bytes (30.68 MB)

✓ 下载完成，文件保存在: /Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/output/test_frontend_download
```

---

### 测试 5: 验证 REAPER 项目可用性

**步骤**：
1. 找到下载的 RPP 文件
2. 在 REAPER 中打开项目
3. 检查所有音频文件是否正确加载

**预期结果**：
- ✅ REAPER 成功打开项目
- ✅ 所有音轨显示正常
- ✅ 没有缺失文件提示

**检查路径**：
```bash
ls -lh output/test_frontend_download/
```

应该看到：
```
drwxr-xr-x  Audio/
-rw-r--r--  test.rpp (41 KB)
-rw-r--r--  test_preview.ogg (156 KB)
```

---

## 🔍 故障排查

### 问题 1: API 服务器未响应

**检查**：
```bash
# 查看日志
tail -f data-pipeline/api.log

# 检查进程
ps aux | grep capsule_api
```

**解决**：
```bash
# 重启 API 服务器
pkill -f capsule_api
cd data-pipeline
./venv/bin/python capsule_api.py > api.log 2>&1 &
```

---

### 问题 2: 上传失败 - 403 Unauthorized

**原因**：Service Role Key 配置错误

**检查**：
```bash
cat data-pipeline/.env.supabase
```

**解决**：
确保 `SUPABASE_SERVICE_ROLE_KEY` 是正确的（以 `eyJ` 开头的长字符串）

---

### 问题 3: Audio 文件夹未上传

**检查后端代码**：
1. 打开 `data-pipeline/capsule_api.py`
2. 搜索 `upload_file`
3. 确认是否有 `file_type='audio_folder'` 的调用

**当前状态**：⚠️ **后端代码可能还没有集成 Audio 文件夹上传**

**需要添加的代码**（在同步流程中）：
```python
# 上传 Audio 文件夹
capsule_dir = capsule_data.get('file_path')
audio_folder = os.path.join(os.path.dirname(capsule_dir), 'Audio')

if os.path.exists(audio_folder):
    print(f"[SYNC] 上传 Audio 文件夹...")
    supabase.upload_file(
        user_id=user_id,
        capsule_local_id=record_id,
        file_type='audio_folder',
        file_path=audio_folder
    )
```

---

## 📊 测试检查清单

### 上传测试
- [ ] 选择一个本地胶囊
- [ ] 点击"同步到云端"
- [ ] 观察上传进度
- [ ] 验证上传成功
- [ ] 检查胶囊状态变为 `synced`
- [ ] 验证云端有对应记录

### 文件验证
- [ ] 预览音频已上传（156 KB）
- [ ] RPP 文件已上传（41 KB）
- [ ] Audio 文件夹已上传（30.68 MB）
- [ ] 所有音频文件都可访问

### 下载测试
- [ ] 从云端获取胶囊列表
- [ ] 选择一个云端胶囊
- [ ] 下载元数据到本地
- [ ] 下载所有文件
- [ ] 验证文件夹结构完整

### REAPER 集成
- [ ] 在 REAPER 中打开下载的 RPP
- [ ] 所有音轨正常显示
- [ ] 音频可以正常播放
- [ ] 没有文件缺失错误

---

## 🎯 下一步

完成前端测试后：
1. ✅ 记录测试结果
2. ⚠️ 修复发现的问题
3. 📝 更新文档
4. 🚀 继续 Phase B6-B8

---

**测试完成后，请告诉我结果，我们可以继续优化！**
