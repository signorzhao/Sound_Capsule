# Phase A 前端集成测试指南

**日期**: 2026-01-10
**状态**: ✅ 集成完成
**测试准备**: 就绪

---

## 🎯 集成完成情况

### ✅ 已完成

1. **ProtectedRoute 组件** - 路由保护
   - 未登录用户自动重定向到登录页
   - 加载状态显示

2. **AppRouter 组件** - 路由配置
   - `/login` - 登录页面（公开）
   - `/register` - 注册页面（公开）
   - `/` - 主应用（需要认证）

3. **main.jsx 更新**
   - 集成 BrowserRouter
   - 集成 AuthProvider
   - 条件启用认证系统

4. **登录/注册页面**
   - 美观的 UI 设计
   - 表单验证
   - 错误处理

---

## 🧪 测试步骤

### 前提条件

确保以下服务正在运行：
1. ✅ API 服务器 (http://localhost:5002)
2. ✅ Vite 开发服务器 (http://localhost:3000)

### 测试流程

#### 1️⃣ 访问应用

打开浏览器访问: http://localhost:3000

**预期结果**:
- 如果未登录 → 自动重定向到 `/login`
- 如果已登录 → 显示主应用

#### 2️⃣ 测试注册

在登录页面点击"立即注册"：

1. 填写注册表单：
   ```
   用户名: testuser001
   邮箱: testuser001@example.com
   密码: TestPass123
   确认密码: TestPass123
   ```

2. 点击"注册"按钮

**预期结果**:
- ✅ 注册成功提示
- ✅ 自动跳转到主应用
- ✅ 可以正常使用所有功能

#### 3️⃣ 测试登录

注销后重新登录：

1. 在登录页面填写：
   ```
   用户名或邮箱: testuser001
   密码: TestPass123
   ```

2. 点击"登录"按钮

**预期结果**:
- ✅ 登录成功
- ✅ 自动跳转到主应用
- ✅ Token 保存在 LocalStorage

#### 4️⃣ 测试路由保护

1. 在浏览器中直接访问: `http://localhost:3000/`
2. 清除 LocalStorage（模拟未登录状态）

**预期结果**:
- ✅ 自动重定向到 `/login`
- ✅ URL 显示 `/login`

#### 5️⃣ 测试 Token 持久化

1. 登录成功后
2. 关闭浏览器标签页
3. 重新打开访问: `http://localhost:3000/`

**预期结果**:
- ✅ 无需重新登录
- ✅ 直接进入主应用

#### 6️⃣ 测试注销

在主应用中（如果有注销按钮）：
1. 点击注销
2. 确认注销

**预期结果**:
- ✅ Token 从 LocalStorage 清除
- ✅ 跳转到登录页面

---

## 🐛 常见问题排查

### 问题 1: 页面空白

**原因**: Vite 服务器未启动或编译错误

**解决**:
```bash
# 检查 Vite 日志
npm run dev

# 查看浏览器控制台错误
```

### 问题 2: API 请求失败

**原因**: API 服务器未启动或端口错误

**解决**:
```bash
# 检查 API 服务器
cd data-pipeline
./venv/bin/python capsule_api.py --port 5002

# 测试 API
curl http://localhost:5002/api/health
```

### 问题 3: 登录后立即跳回登录页

**原因**: Token 未正确保存或验证失败

**解决**:
1. 打开浏览器控制台
2. 检查 LocalStorage 是否有 `access_token` 和 `refresh_token`
3. 检查 Network 标签的 API 响应

### 问题 4: 注册提示用户已存在

**解决**:
1. 使用不同的用户名/邮箱
2. 或在数据库中删除旧用户：
```python
# data-pipeline
./venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('database/capsules.db')
conn.execute('DELETE FROM users WHERE username = ?', ('testuser001',))
conn.commit()
print('用户已删除')
"
```

---

## 📊 调试工具

### 1. 检查认证状态

打开浏览器控制台执行：
```javascript
// 检查 LocalStorage
console.log('Access Token:', localStorage.getItem('access_token'));
console.log('Refresh Token:', localStorage.getItem('refresh_token'));

// 检查用户信息
// (需要在 App 组件内部)
```

### 2. 手动测试 API

```bash
# 测试登录
curl -X POST http://localhost:5002/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"login": "testuser001", "password": "TestPass123"}'

# 测试获取用户信息（替换 TOKEN）
curl -X GET http://localhost:5002/api/auth/me \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

### 3. 查看数据库

```bash
# 查看所有用户
cd data-pipeline
./venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('database/capsules.db')
cursor = conn.execute('SELECT id, username, email, created_at FROM users')
for row in cursor:
    print(f'ID: {row[0]}, 用户名: {row[1]}, 邮箱: {row[2]}, 创建时间: {row[3]}')
"
```

---

## ✅ 测试清单

- [ ] 未登录访问主应用 → 重定向到登录页
- [ ] 注册新用户 → 成功并跳转
- [ ] 登录现有用户 → 成功并跳转
- [ ] Token 持久化 → 关闭浏览器后仍有效
- [ ] Token 过期处理 → 自动刷新或提示重新登录
- [ ] 注销功能 → 清除 Token 并跳转
- [ ] 错误密码 → 显示错误提示
- [ ] 用户名已存在 → 显示错误提示

---

## 🎨 UI 预览

### 登录页面
- 渐变紫色背景
- 白色卡片居中
- 用户名/邮箱/密码输入框
- "立即注册"链接

### 注册页面
- 相同的 UI 设计
- 额外的确认密码字段
- 密码要求提示
- "已有账户？立即登录"链接

### 加载状态
- 旋转的加载动画
- "加载中..."文字
- 居中显示

---

## 🚀 下一步

测试通过后，可以继续：

1. **添加更多认证功能**
   - 忘记密码
   - 邮箱验证
   - OAuth 第三方登录

2. **完善用户体验**
   - 记住我功能
   - 自动登录
   - Token 自动刷新

3. **开始 Phase B**
   - 云端同步设计
   - 数据同步机制

---

**祝测试顺利！** 🎉
