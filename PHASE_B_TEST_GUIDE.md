# Phase B: 云端同步系统测试指南

**日期**: 2026-01-10
**状态**: 开发完成，待测试
**版本**: v1.0

---

## 📋 测试前准备

### 1. 确认依赖已安装

```bash
# 进入项目目录
cd /Users/ianzhao/Desktop/Sound_Capsule/synesth

# 确认 Python 后端运行
# 检查 Flask API 是否在 http://localhost:5002 运行

# 确认前端开发服务器运行
# npm run dev 应该在 http://localhost:3000 运行
```

### 2. 确认数据库已初始化

```bash
# 检查同步表是否存在
cd data-pipeline
python3 -c "
from capsule_api import get_database
import sqlite3

db = get_database()
cursor = db.cursor()

# 检查同步表
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'sync%'\")
tables = cursor.fetchall()
print('同步表:', [t[0] for t in tables])
"
```

**预期输出**:
```
同步表: ['sync_status', 'sync_log', 'sync_conflicts']
```

### 3. 确认已登录

- 打开浏览器访问 http://localhost:3000
- 确认已登录（如果未登录，使用测试账户登录）
- 确认右上角显示用户菜单

---

## ✅ 测试步骤

### 测试 1: 查看同步指示器

**步骤**:
1. 打开主应用 (http://localhost:3000)
2. 查看页面右上角

**预期结果**:
- [ ] 在用户菜单左侧看到同步图标（云图标）
- [ ] 图标状态显示为"已同步"（绿色云图标）
- [ ] 没有徽章显示（pendingCount = 0）

**实际结果**: ___________________

**截图**:
```
（描述或粘贴截图）
```

---

### 测试 2: 点击同步按钮查看菜单

**步骤**:
1. 点击同步图标按钮
2. 观察下拉菜单

**预期结果**:
- [ ] 下拉菜单向下滑入（动画效果）
- [ ] 显示"云端同步"标题
- [ ] 显示最后同步时间
- [ ] 显示待同步数量: 0 项
- [ ] 显示"立即同步"按钮
- [ ] 显示说明文字："数据变更后 30 秒自动同步"

**实际结果**: ___________________

**显示的信息**:
```
最后同步: ___________________
待同步: ___________________
```

---

### 测试 3: 手动触发同步

**步骤**:
1. 点击"立即同步"按钮
2. 观察按钮状态变化
3. 打开浏览器开发者工具 (F12) 查看 Console 和 Network

**预期结果**:
- [ ] 按钮变为"同步中..."
- [ ] 图标变为旋转的刷新图标
- [ ] Network 标签看到请求:
  - `POST /api/sync/upload`
  - `GET /api/sync/download`
- [ ] Console 看到 "开始同步..." 日志
- [ ] Console 看到 "同步完成" 日志
- [ ] 3 秒后菜单自动关闭

**实际结果**: ___________________

**Network 请求状态**:
```
/api/sync/upload: 状态码 _________
/api/sync/download: 状态码 _________
```

**Console 日志**:
```
（复制相关日志）
```

---

### 测试 4: 标记记录为待同步

**步骤**:
1. 打开浏览器 Console (F12)
2. 执行以下代码:

```javascript
// 标记一个胶囊为待同步
fetch('http://localhost:5002/api/sync/mark-pending', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + localStorage.getItem('access_token')
  },
  body: JSON.stringify({
    table_name: 'capsules',
    record_id: 1,
    operation: 'update'
  })
})
.then(r => r.json())
.then(data => {
  console.log('标记结果:', data);
  location.reload(); // 刷新页面查看更新
});
```

**预期结果**:
- [ ] Console 输出: `{"success": true, "message": "已标记为待同步"}`
- [ ] 页面刷新后，同步图标显示黄色徽章 "1"
- [ ] 点击同步图标，菜单显示"待同步: 1 项"

**实际结果**: ___________________

---

### 测试 5: 同步待同步的记录

**步骤**:
1. 点击同步按钮（带徽章状态）
2. 观察同步过程
3. 同步完成后，点击再次查看菜单

**预期结果**:
- [ ] 同步开始，徽章消失
- [ ] 同步完成后，徽章不再显示
- [ ] 菜单显示"待同步: 0 项"
- [ ] 图标变回绿色"已同步"状态

**实际结果**: ___________________

---

### 测试 6: 检查同步状态 API

**步骤**:
1. 打开 Console 执行:

```javascript
fetch('http://localhost:5002/api/sync/status', {
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('access_token')
  }
})
.then(r => r.json())
.then(data => console.log('同步状态:', data));
```

**预期结果**:
- [ ] 返回成功响应
- [ ] 数据包含:
  - `last_sync_at`: 最后同步时间
  - `pending_count`: 待同步数量
  - `conflict_count`: 冲突数量
  - `synced_count`: 已同步数量

**实际结果**: ___________________

**API 响应**:
```json
（粘贴响应数据）
```

---

### 测试 7: 获取待同步记录

**步骤**:
1. 先标记几条记录为待同步（使用测试 4 的方法）
2. 执行:

```javascript
fetch('http://localhost:5002/api/sync/pending?table=capsules', {
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('access_token')
  }
})
.then(r => r.json())
.then(data => console.log('待同步记录:', data));
```

**预期结果**:
- [ ] 返回待同步记录列表
- [ ] 每条记录包含:
  - `table_name`: 表名
  - `record_id`: 记录 ID
  - `sync_state`: 'pending'
  - `local_version`: 本地版本号

**实际结果**: ___________________

---

### 测试 8: 错误处理

**步骤**:
1. 停止 Python 后端 (Ctrl+C)
2. 点击同步按钮
3. 观察错误提示

**预期结果**:
- [ ] 同步失败
- [ ] 图标变为红色错误状态
- [ ] 点击查看菜单，显示错误信息
- [ ] 菜单显示红色错误条目
- [ ] 重启后端后，可以重新同步

**实际结果**: ___________________

**错误信息**: ___________________

---

### 测试 9: 冲突处理（模拟）

**步骤**:
1. 在数据库中手动插入冲突记录:

```bash
cd data-pipeline
python3 -c "
from capsule_api import get_database
import json

db = get_database()
cursor = db.cursor()

# 插入测试冲突
cursor.execute('''
  INSERT INTO sync_conflicts (table_name, record_id, local_data, cloud_data, conflict_type)
  VALUES (?, ?, ?, ?, ?)
''', (
  'capsules',
  1,
  json.dumps({'id': 1, 'name': '本地版本'}),
  json.dumps({'id': 1, 'name': '云端版本'}),
  'data_conflict'
))

db.commit()
print('冲突记录已插入')

# 查询冲突
cursor.execute('SELECT * FROM sync_conflicts WHERE resolved=0')
conflicts = cursor.fetchall()
print('当前冲突数:', len(conflicts))
"
```

2. 刷新浏览器页面
3. 查看同步指示器

**预期结果**:
- [ ] 同步图标显示红色冲突徽章
- [ ] 徽章显示冲突数量
- [ ] 点击菜单，显示"冲突: 1 项"（红色）

**实际结果**: ___________________

4. 测试解决冲突:

```javascript
fetch('http://localhost:5002/api/sync/resolve-conflict', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + localStorage.getItem('access_token')
  },
  body: JSON.stringify({
    conflict_id: 1,
    resolution: 'local'  // 或 'cloud'
  })
})
.then(r => r.json())
.then(data => {
  console.log('解决冲突结果:', data);
  location.reload();
});
```

**预期结果**:
- [ ] 返回成功响应
- [ ] 刷新后冲突徽章消失
- [ ] 菜单不再显示冲突

**实际结果**: ___________________

---

### 测试 10: 自动同步（观察）

**步骤**:
1. 标记一条记录为待同步
2. 不要点击同步按钮
3. 观察页面，等待 30 秒
4. 观察 Console 日志

**预期结果**:
- [ ] 30 秒后自动触发同步
- [ ] Console 输出: "自动同步触发"
- [ ] 同步自动执行
- [ ] 同步完成后，待同步徽章消失

**实际结果**: ___________________

**自动同步触发时间**: ___________________

---

## 🐛 问题记录

### 发现的问题

| # | 问题描述 | 严重程度 | 状态 |
|---|---------|---------|------|
| 1 | | 🔴 Critical ⚠️ Major 🔵 Minor | 🅾️ Open ✅ Fixed |
| 2 | | | |

### 问题描述
```
（记录发现的任何问题）
```

---

## 💬 反馈

### UI 评价
- 同步图标位置: ⭐⭐⭐⭐⭐
- 同步状态指示: ⭐⭐⭐⭐⭐
- 下拉菜单布局: ⭐⭐⭐⭐⭐
- 动画效果: ⭐⭐⭐⭐⭐

### 功能评价
- 手动同步速度: ⭐⭐⭐⭐⭐
- 自动同步可靠性: ⭐⭐⭐⭐⭐
- 错误提示清晰度: ⭐⭐⭐⭐⭐
- 状态显示准确性: ⭐⭐⭐⭐⭐

### 改进建议
```
（请记录您的建议）
```

---

## ✅ 测试总结

### 通过的测试
- [ ] 测试 1: 查看同步指示器
- [ ] 测试 2: 点击同步按钮查看菜单
- [ ] 测试 3: 手动触发同步
- [ ] 测试 4: 标记记录为待同步
- [ ] 测试 5: 同步待同步的记录
- [ ] 测试 6: 检查同步状态 API
- [ ] 测试 7: 获取待同步记录
- [ ] 测试 8: 错误处理
- [ ] 测试 9: 冲突处理
- [ ] 测试 10: 自动同步

### 测试结果
- 总测试数: 10
- 通过: ___
- 失败: ___
- 通过率: ___%

### 总体评价
- [ ] ✅ 所有功能正常
- [ ] ⚠️ 有小问题，但不影响使用
- [ ] ❌ 有严重问题，需要修复

---

## 📊 Phase B 实施总结

### 已完成的功能

#### 后端
- ✅ 同步数据库表 (sync_status, sync_log, sync_conflicts)
- ✅ 同步服务模块 (sync_service.py)
- ✅ 7 个同步 API 端点
  - `/api/sync/status` - 获取同步状态
  - `/api/sync/pending` - 获取待同步记录
  - `/api/sync/mark-pending` - 标记待同步
  - `/api/sync/upload` - 上传到云端
  - `/api/sync/download` - 从云端下载
  - `/api/sync/conflicts` - 获取冲突
  - `/api/sync/resolve-conflict` - 解决冲突

#### 前端
- ✅ SyncContext - 同步状态管理
- ✅ SyncIndicator - 同步指示器 UI
- ✅ 集成到主应用
- ✅ 自动同步逻辑（30 秒延迟）
- ✅ 网络恢复自动同步
- ✅ 同步完成事件通知

### 待完成的功能（后续 Phase）

#### 云端 API 实现
- ⏳ 实际的云端服务器（当前为模拟）
- ⏳ 真实的上传/下载逻辑
- ⏳ 云端数据库集成

#### 高级同步功能
- ⏳ 增量同步优化
- ⏳ 文件同步（RPP 文件、音频预览）
- ⏳ 离线队列管理
- ⏳ 同步历史查询

---

**测试完成时间**: _______________
**测试人员**: _______________

**Phase B 状态**: 🅾️ 开发完成，待测试验证
