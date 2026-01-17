# 🎯 Phase A 前端集成测试说明

## 📊 当前状态

**所有服务已就绪！** ✅

- ✅ API 服务器: http://localhost:5002
- ✅ 前端服务器: http://localhost:3000
- ✅ 数据库: 已清理，无测试用户
- ✅ 认证系统: 已启用

---

## 🚀 快速开始

### 1. 打开浏览器

访问: **http://localhost:3000**

### 2. 预期看到

您应该看到一个**紫色渐变背景的登录页面**：

```
┌─────────────────────────────────┐
│                                 │
│      Sound Capsule              │
│   登录到您的账户                │
│                                 │
│  ┌──────────────────────────┐  │
│  │ 用户名或邮箱             │  │
│  └──────────────────────────┘  │
│                                 │
│  ┌──────────────────────────┐  │
│  │ 密码                     │  │
│  └──────────────────────────┘  │
│                                 │
│     [ 登录 ]                    │
│                                 │
│  还没有账户？立即注册           │
│                                 │
└─────────────────────────────────┘
```

### 3. 测试流程

#### 步骤 1: 注册新账户

1. 点击 **"立即注册"**
2. 填写表单：
   ```
   用户名: demo001
   邮箱: demo001@example.com
   密码: DemoPass123
   确认密码: DemoPass123
   ```
3. 点击 **"注册"**
4. ✅ 成功后会自动跳转到主应用

#### 步骤 2: 验证登录状态

打开浏览器开发者工具 (F12)：
- **Application** → **Local Storage**
- 应该看到:
  - `access_token`: eyJhbGciOi...
  - `refresh_token`: 550e8400-...

#### 步骤 3: 测试持久化

1. 关闭浏览器标签页
2. 重新打开访问 http://localhost:3000
3. ✅ 应该直接进入主应用（无需重新登录）

#### 步骤 4: 测试注销（手动）

1. 打开开发者工具 → Console
2. 执行: `localStorage.clear()`
3. 刷新页面 (Cmd+R)
4. ✅ 应该跳转到登录页面

#### 步骤 5: 重新登录

1. 使用之前注册的账户登录
2. ✅ 应该能成功登录并进入主应用

---

## 🔍 调试工具

### 检查认证状态

打开浏览器 Console (F12) 执行：

```javascript
// 查看存储的 Token
console.log('Access Token:', localStorage.getItem('access_token'));
console.log('Refresh Token:', localStorage.getItem('refresh_token'));

// 查看当前 URL
console.log('Current URL:', window.location.href);
```

### 检查 API 请求

打开开发者工具 → **Network** 标签：
- 注册时应该看到: `POST /api/auth/register`
- 登录时应该看到: `POST /api/auth/login`
- 获取用户信息: `GET /api/auth/me`

### 查看数据库

```bash
cd data-pipeline
./venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('database/capsules.db')
cursor = conn.execute('SELECT id, username, email FROM users')
for row in cursor:
    print(f'ID: {row[0]}, 用户名: {row[1]}, 邮箱: {row[2]}')
"
```

---

## ⚠️ 常见问题

### Q1: 页面空白或加载失败

**解决**:
1. 检查前端服务器是否运行
2. 打开 Console 查看错误信息
3. 尝试刷新页面 (Cmd+Shift+R)

### Q2: 注册/登录按钮点击无反应

**解决**:
1. 检查 API 服务器是否运行
2. 打开 Network 标签查看请求
3. 查看 Console 的错误信息

### Q3: 登录后立即跳回登录页

**解决**:
1. 打开 Console 查看错误
2. 检查 Network 标签的 API 响应
3. 确认 Token 是否正确保存

### Q4: 提示"用户已存在"

**解决**:
使用不同的用户名，或清理数据库：
```bash
cd data-pipeline
./venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('database/capsules.db')
conn.execute('DELETE FROM users WHERE username = ?', ('demo001',))
conn.commit()
print('用户已删除')
"
```

---

## ✅ 测试清单

完整的测试清单请查看：
**📄 [PHASE_A_TESTING_CHECKLIST.md](PHASE_A_TESTING_CHECKLIST.md)**

包含 8 个测试场景的详细步骤。

---

## 📊 测试完成后

### 如果一切正常 ✅

恭喜！Phase A 认证系统完全可用！

可以继续：
- Phase B: 云端同步系统
- Phase C: 权限和共享系统

### 如果发现问题 ⚠️

请记录：
1. 问题的具体表现
2. Console 的错误信息
3. Network 的请求/响应
4. 复现步骤

然后报告问题，我会帮您修复。

---

## 📞 需要帮助？

如果测试过程中遇到任何问题：

1. 查看浏览器 Console (F12 → Console)
2. 查看 Network 标签 (F12 → Network)
3. 查看服务器日志:
   - API: `data-pipeline/export_debug.log`
   - 前端: 终端输出

---

**祝测试顺利！** 🎉

准备好后，打开浏览器开始测试吧！
