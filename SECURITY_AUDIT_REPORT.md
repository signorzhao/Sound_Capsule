# Sound Capsule 全量安全审查报告

**审查日期**: 2026-03-11
**审查范围**: 全项目代码（后端 Python Flask、前端 React、Tauri/Rust 桌面端、配置文件）
**审查结果**: 6 个高危、6 个中危、3 个低危

---

## 目录

- [HIGH 严重级别](#high-严重级别)
  - [漏洞 1: JWT 签名密钥硬编码为弱默认值](#漏洞-1-jwt-签名密钥硬编码为弱默认值)
  - [漏洞 2: JWT 无签名验证的回退机制](#漏洞-2-jwt-无签名验证的回退机制)
  - [漏洞 3: Supabase API Key 硬编码在已提交的源文件中](#漏洞-3-supabase-api-key-硬编码在已提交的源文件中)
  - [漏洞 4: Tauri CSP 被完全禁用](#漏洞-4-tauri-csp-被完全禁用)
  - [漏洞 5: open_rpp_in_reaper 可打开任意文件](#漏洞-5-open_rpp_in_reaper-可打开任意文件)
  - [漏洞 6: JWT Token 存储在 localStorage](#漏洞-6-jwt-token-存储在-localstorage)
- [MEDIUM 严重级别](#medium-严重级别)
  - [漏洞 7: CORS 默认允许所有来源](#漏洞-7-cors-默认允许所有来源)
  - [漏洞 8: shell:allow-execute 权限过于宽泛](#漏洞-8-shellallow-execute-权限过于宽泛)
  - [漏洞 9: .env.supabase 使用 HTTP 连接](#漏洞-9-envsupabase-使用-http-连接)
  - [漏洞 10: 云端 API 默认使用 HTTP + 内网 IP 硬编码](#漏洞-10-云端-api-默认使用-http--内网-ip-硬编码)
  - [漏洞 11: 部分 Flask 服务绑定 0.0.0.0](#漏洞-11-部分-flask-服务绑定-0000)
  - [漏洞 12: .env.supabase.example 泄露真实 Supabase URL](#漏洞-12-envsupabaseexample-泄露真实-supabase-url)
- [LOW 严重级别](#low-严重级别)
  - [漏洞 13-15: 多个组件硬编码 localhost URL 且不携带认证](#漏洞-13-15-多个组件硬编码-localhost-url-且不携带认证)
- [修复优先级总表](#修复优先级总表)

---

## HIGH 严重级别

### 漏洞 1: JWT 签名密钥硬编码为弱默认值

| 属性 | 值 |
|------|-----|
| **文件** | `data-pipeline/auth.py` 第 33 行 |
| **严重级别** | HIGH |
| **置信度** | 10/10 |
| **分类** | 认证漏洞 / 硬编码密钥 |

**描述**

```python
SECRET_KEY = "synesth-secret-key-change-in-production"  # TODO: 从环境变量读取
```

JWT 签名密钥被硬编码为一个弱字符串，注释中标注了 TODO 但从未实现从环境变量读取。该密钥用于签发和验证本地认证模式的所有 JWT Token。

**攻击场景**

任何能看到源码的人（包括仓库协作者、代码泄露场景）都可以使用这个已知密钥伪造任意用户的 JWT Token，完全绕过认证系统，以任何用户身份访问所有 API。

**修复建议**

```python
import os

SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY environment variable is required")
```

同时在 `.env.example` 中添加：
```
JWT_SECRET_KEY=your-random-secret-key-here
```

---

### 漏洞 2: JWT 无签名验证的回退机制

| 属性 | 值 |
|------|-----|
| **文件** | `data-pipeline/routes/library_routes.py` 第 85-102 行；`data-pipeline/capsule_download_api.py` 第 139-143 行 |
| **严重级别** | HIGH |
| **置信度** | 8/10 |
| **分类** | 认证绕过 |

**描述**

`_extract_supabase_sub_from_bearer` 函数仅进行 Base64 解码提取 JWT payload 中的 `sub` 字段，**完全不验证签名**。注释声称"仅用于归属识别/展示，不用于权限提升"，但在 `capsule_download_api.py` 的下载逻辑中，当 `verify_access_token` 失败时，回退使用该函数提取的 `user_id` 来执行实际的数据库操作和文件下载。

**攻击场景**

攻击者可以构造一个包含任意 `sub` 值的伪造 JWT Token（无需知道签名密钥），绕过认证，以任意用户身份下载胶囊文件和读取数据。

**修复建议**

移除无签名验证的回退路径。当 `verify_access_token` 失败时，应直接返回 `401 Unauthorized` 错误，不应尝试从未验证的 Token 中提取用户身份。

---

### 漏洞 3: Supabase API Key 硬编码在已提交的源文件中

| 属性 | 值 |
|------|-----|
| **文件** | `data-pipeline/setup_supabase.py` 第 12 行 |
| **严重级别** | HIGH |
| **置信度** | 10/10 |
| **分类** | 密钥泄露 |

**描述**

```python
SUPABASE_KEY = "sb_publishable_IXJZMBYmusLOEuKoydTbMg_42F5XVSu"
```

Supabase API Key 和项目 URL 被硬编码在已提交到 git 的源文件中。`git ls-files` 确认该文件在版本控制中。

**攻击场景**

如果仓库曾经公开或被泄露，攻击者可以使用该密钥直接访问 Supabase 项目的 API，读写数据库中的数据。即使密钥已经被轮换，git 历史中仍然保留着明文密钥。

**修复建议**

1. **立即**轮换 Supabase 项目的所有 API 密钥
2. 使用 BFG Repo Cleaner 从 git 历史中清除该密钥：
   ```bash
   bfg --replace-text passwords.txt repo.git
   ```
3. 将 `setup_supabase.py` 改为从环境变量读取密钥
4. 在 `.gitignore` 中添加 `test_supabase_*.py`

---

### 漏洞 4: Tauri CSP 被完全禁用

| 属性 | 值 |
|------|-----|
| **文件** | `webapp/src-tauri/tauri.conf.json` 第 25 行 |
| **严重级别** | HIGH |
| **置信度** | 10/10 |
| **分类** | 配置缺陷 / XSS 防护缺失 |

**描述**

```json
"csp": null
```

Content Security Policy 被完全禁用。CSP 是 Tauri 应用防御 XSS 攻击的核心防线。当 CSP 为 null 时，任何注入的脚本都可以不受限制地执行，包括加载远程脚本、执行内联代码、连接任意外部服务器。

**攻击场景**

如果前端存在任何 XSS 漏洞（如用户输入未转义），攻击者可以注入任意 JavaScript，进而通过 Tauri IPC 调用已注册的命令（如 `open_rpp_in_reaper`、`save_app_config` 等），实现本地文件操作和任意命令执行。

**修复建议**

```json
"security": {
  "csp": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' http://127.0.0.1:5002 http://127.0.0.1:5003"
}
```

---

### 漏洞 5: open_rpp_in_reaper 可打开任意文件

| 属性 | 值 |
|------|-----|
| **文件** | `webapp/src-tauri/src/sidecar.rs` 第 348-421 行 |
| **严重级别** | HIGH |
| **置信度** | 8/10 |
| **分类** | 路径遍历 / 任意代码执行 |

**描述**

```rust
#[tauri::command]
pub fn open_rpp_in_reaper(path: String) -> Result<String, String> {
    let file_path = Path::new(&path);
    if !file_path.exists() { ... }
    // 直接用系统命令打开，无路径或类型验证
    Command::new("open").arg(&path).spawn();
}
```

该 Tauri 命令接收任意 `path` 参数，仅检查文件是否存在，不验证文件扩展名和路径范围，直接使用系统的 `open`（macOS）或 `cmd /C start`（Windows）打开。

**攻击场景**

结合 CSP 被禁用（漏洞 4），如果存在 XSS 漏洞，攻击者可以调用：
```javascript
invoke('open_rpp_in_reaper', { path: '/path/to/malicious.exe' })
```
在 Windows 上，`cmd /C start "" "C:\path\to\malicious.exe"` 可以直接执行恶意程序。

**修复建议**

```rust
let canonical = file_path.canonicalize().map_err(|e| e.to_string())?;

// 1. 验证扩展名
if !canonical.extension().map_or(false, |ext| ext == "rpp") {
    return Err("仅支持 .rpp 文件".to_string());
}

// 2. 验证路径在允许的目录内
let allowed_dir = get_export_directory()?;
if !canonical.starts_with(&allowed_dir) {
    return Err("路径不在允许的目录范围内".to_string());
}
```

---

### 漏洞 6: JWT Token 存储在 localStorage

| 属性 | 值 |
|------|-----|
| **文件** | `webapp/src/contexts/AuthContext.jsx` 第 30, 45, 115-116 行；`webapp/src/utils/apiClient.js` 第 15, 35 行 |
| **严重级别** | HIGH |
| **置信度** | 10/10 |
| **分类** | 会话管理缺陷 |

**描述**

access_token 和 refresh_token 均存储在 `localStorage` 中。localStorage 对同源下的任意 JavaScript 完全可见，无法设置过期时间，也无法通过 httpOnly 标记阻止脚本读取。

**攻击场景**

如果攻击者通过任何途径（第三方依赖供应链攻击、浏览器扩展注入、XSS 漏洞等）执行了任意 JavaScript，可直接通过以下代码窃取两个 Token：

```javascript
localStorage.getItem('access_token')
localStorage.getItem('refresh_token')
```

refresh_token 的泄露尤其严重，因为攻击者可用它长期获取新的 access_token，实现持久会话劫持。

**修复建议**

1. 将 refresh_token 存储在后端设置的 `httpOnly` + `Secure` + `SameSite=Strict` Cookie 中
2. access_token 仅保留在内存中（React state/context），不持久化到 localStorage
3. 页面刷新时通过 httpOnly Cookie 中的 refresh_token 静默获取新的 access_token
4. 如果必须使用 localStorage（Tauri 桌面环境无 Cookie），至少缩短 access_token 有效期到 5-15 分钟，并实现 refresh_token rotation

---

## MEDIUM 严重级别

### 漏洞 7: CORS 默认允许所有来源

| 属性 | 值 |
|------|-----|
| **文件** | `data-pipeline/capsule_api.py` 第 169-173 行 |
| **严重级别** | MEDIUM |
| **置信度** | 9/10 |
| **分类** | 配置缺陷 |

**描述**

```python
cors_allow_all = str(os.getenv('CORS_ALLOW_ALL', 'true')).lower() == 'true'
# ...
"origins": "*" if cors_allow_all else cors_origins,
```

`CORS_ALLOW_ALL` 环境变量默认值为 `'true'`，导致任何网站都可以向该 API 发起跨域请求。

**攻击场景**

在桌面应用场景下，如果用户的浏览器访问了恶意网站，该网站可以向本地运行的 API（localhost:5002）发起请求，读取用户的胶囊数据、修改配置或触发导出操作。

**修复建议**

将 `CORS_ALLOW_ALL` 默认值改为 `'false'`，仅允许已知的本地来源：

```python
cors_allow_all = str(os.getenv('CORS_ALLOW_ALL', 'false')).lower() == 'true'
```

---

### 漏洞 8: shell:allow-execute 权限过于宽泛

| 属性 | 值 |
|------|-----|
| **文件** | `webapp/src-tauri/capabilities/default.json` 第 18 行 |
| **严重级别** | MEDIUM |
| **置信度** | 8/10 |
| **分类** | 权限配置缺陷 |

**描述**

`shell:allow-execute` 允许前端通过 Tauri Shell 插件执行任意系统命令。Tauri 2.0 的安全模型推荐使用 scoped commands 来限制可执行的命令范围。

**攻击场景**

结合 CSP 被禁用（漏洞 4），XSS 攻击者可以通过 Shell 插件执行任意系统命令，实现完全的远程代码执行（RCE）。

**修复建议**

使用 scoped 配置限制可执行的命令：

```json
"shell": {
  "open": true,
  "scope": [
    {
      "name": "open-reaper",
      "cmd": "open",
      "args": [{ "validator": "\\S+\\.rpp$" }]
    }
  ]
}
```

---

### 漏洞 9: .env.supabase 使用 HTTP 连接

| 属性 | 值 |
|------|-----|
| **文件** | `data-pipeline/.env.supabase` 第 2 行 |
| **严重级别** | MEDIUM |
| **置信度** | 9/10 |
| **分类** | 传输安全 |

**描述**

```
SUPABASE_URL=http://192.168.31.71:8000
```

使用明文 HTTP 协议连接到内网 IP 上的 Supabase 实例。所有与 Supabase 的通信（包括认证 Token 和用户数据）都通过未加密的 HTTP 传输。

**攻击场景**

同一局域网的攻击者可以通过 ARP 欺骗或网络嗅探截获所有 API 请求，获取 Supabase JWT Token 和传输中的用户数据。

**修复建议**

为私有 Supabase 实例配置 TLS 证书（如使用 Let's Encrypt 或自签名证书），将连接改为 HTTPS。

---

### 漏洞 10: 云端 API 默认使用 HTTP + 内网 IP 硬编码

| 属性 | 值 |
|------|-----|
| **文件** | `webapp/src/utils/apiOrigins.js` 第 1-2 行 |
| **严重级别** | MEDIUM |
| **置信度** | 9/10 |
| **分类** | 传输安全 / 配置缺陷 |

**描述**

```javascript
const LOCAL_API_ORIGIN = import.meta.env.VITE_LOCAL_API_ORIGIN || 'http://127.0.0.1:5003';
const CLOUD_API_ORIGIN = import.meta.env.VITE_CLOUD_API_ORIGIN || 'http://192.168.31.71:5002';
```

云端 API fallback 值使用 `http://` 指向内网 IP。通过 HTTP 传输的 JWT Token 和用户凭据可被中间人截获。

**攻击场景**

在同一网络下的攻击者可通过 ARP 欺骗或 WiFi 嗅探拦截用户的认证请求，获取明文传输的 access_token、refresh_token，以及登录时的用户名/密码。

**修复建议**

1. 云端 API 的默认 fallback 值应使用 HTTPS URL
2. 移除硬编码的内网 IP，将其仅放置在 `.env.development` 文件中
3. 在生产构建中验证 `CLOUD_API_ORIGIN` 必须为 HTTPS

---

### 漏洞 11: 部分 Flask 服务绑定 0.0.0.0

| 属性 | 值 |
|------|-----|
| **文件** | `data-pipeline/service_manager.py` 第 989 行 |
| **严重级别** | MEDIUM |
| **置信度** | 8/10 |
| **分类** | 网络暴露 |

**描述**

Flask 服务绑定到 `0.0.0.0`，监听所有网络接口，包括局域网。

**攻击场景**

在公共 WiFi 或共享网络环境中，局域网内的其他设备可以直接访问该 API 服务，读取用户数据或执行操作。结合 CORS `*` 配置（漏洞 7），风险进一步放大。

**修复建议**

将所有 Flask 服务的 host 改为 `127.0.0.1`，仅允许本地访问：

```python
app.run(host='127.0.0.1', port=port)
```

---

### 漏洞 12: .env.supabase.example 泄露真实 Supabase URL

| 属性 | 值 |
|------|-----|
| **文件** | `data-pipeline/.env.supabase.example` 第 4 行 |
| **严重级别** | MEDIUM |
| **置信度** | 9/10 |
| **分类** | 信息泄露 |

**描述**

```
SUPABASE_URL=https://mngtddqjbbrdwwfxcvxg.supabase.co
```

example 文件中包含真实的 Supabase 项目 URL（不是占位符），已提交到 git。

**攻击场景**

结合泄露的 API Key（漏洞 3），攻击者可以直接定位和访问你的 Supabase 后端。

**修复建议**

替换为占位符：

```
SUPABASE_URL=https://your-project-id.supabase.co
```

---

## LOW 严重级别

### 漏洞 13-15: 多个组件硬编码 localhost URL 且不携带认证

| 属性 | 值 |
|------|-----|
| **文件** | `webapp/src/components/CapsuleExportWizard.jsx` 第 265, 314, 532 行；`webapp/src/components/CacheManager.jsx` 第 22, 53, 82 行；`webapp/src/components/UserMenu.jsx` 第 125-135, 161 行 |
| **严重级别** | LOW |
| **置信度** | 9/10 |
| **分类** | 认证缺失 / 一致性问题 |

**描述**

多个 React 组件直接使用 `fetch('http://localhost:5002/...')` 或 `fetch('http://localhost:5001/...')`，绕过了集中配置的 API 地址（`apiOrigins.js`）和认证封装（`authFetch`），不携带 Authorization Header。

其中包括破坏性操作如 `reset-local-db`（数据库重置）也没有认证保护。

**攻击场景**

如果存在同源页面上的恶意脚本或浏览器扩展，可以直接调用 `http://127.0.0.1:5003/api/config/reset-local-db` 清空本地数据库。

**修复建议**

统一使用 `apiOrigins.js` 中的常量和 `authFetch` 封装：

```javascript
// 替换前
const response = await fetch('http://localhost:5002/api/capsules');

// 替换后
import { authFetch } from '../utils/apiClient';
const response = await authFetch(`${LOCAL_API_BASE}/capsules`);
```

---

## 修复优先级总表

| 优先级 | 漏洞编号 | 描述 | 严重级别 | 预估工作量 |
|--------|---------|------|---------|-----------|
| **P0** | #1 | JWT 硬编码密钥 | HIGH | 10 分钟 |
| **P0** | #2 | JWT 无签名回退 | HIGH | 30 分钟 |
| **P0** | #3 | Supabase Key 泄露 | HIGH | 30 分钟 |
| **P0** | #4 | CSP 禁用 | HIGH | 15 分钟 |
| **P1** | #5 | 任意文件打开 | HIGH | 30 分钟 |
| **P1** | #6 | Token 存储方式 | HIGH | 2 小时 |
| **P1** | #7 | CORS 配置 | MEDIUM | 10 分钟 |
| **P1** | #8 | Shell 权限范围 | MEDIUM | 1 小时 |
| **P2** | #9 | HTTP 连接 Supabase | MEDIUM | 15 分钟 |
| **P2** | #10 | 云端 API HTTP + 内网 IP | MEDIUM | 15 分钟 |
| **P2** | #11 | Flask 绑定 0.0.0.0 | MEDIUM | 15 分钟 |
| **P2** | #12 | Example 文件泄露 URL | MEDIUM | 5 分钟 |
| **P3** | #13-15 | 硬编码 localhost URL | LOW | 各 10 分钟 |

---

## 安全亮点（做得好的地方）

| 检查类别 | 结论 |
|---------|------|
| **dangerouslySetInnerHTML** | 所有 React 组件中未发现使用，安全地依赖 React 的默认转义 |
| **前端硬编码密钥** | 未发现硬编码的 API 密钥或密码，敏感值通过环境变量管理 |
| **XSS (DOM 操作)** | 未发现 `innerHTML`、`eval()`、`new Function()` 等危险操作 |
| **开放重定向** | 未发现基于用户输入的重定向，登录后使用硬编码路径 |
| **密码存储** | 使用 bcrypt 12 轮加盐散列，符合安全最佳实践 |
| **输入过滤** | 登录/注册页面对用户输入进行了字符过滤和长度验证 |
| **SQL 注入** | 数据库操作使用了参数化查询，未发现 SQL 拼接 |

---

## 分阶段改进计划

### 第一阶段：安全立即修复（不影响现有功能）

> 这些修改只涉及代码层面的调整，不改变通信方式和架构，修完后功能完全不受影响。

| 序号 | 对应漏洞 | 具体操作 | 影响评估 |
|------|---------|---------|---------|
| 1 | #1 JWT 硬编码密钥 | `auth.py` 中 `SECRET_KEY` 改为从 `.env` 读取，在 `.env` 中设置当前同样的值 | 无影响，只是换了读取方式 |
| 2 | #3 Supabase Key 泄露 | 将 `setup_supabase.py` 中的硬编码 Key 改为从 `.env` 读取，用 BFG 清理 git 历史 | 无影响，Key 值不变 |
| 3 | #12 Example 文件泄露 | `.env.supabase.example` 和 `.env.example` 中的真实值替换为占位符 | 无影响，example 文件不参与运行 |
| 4 | #13-15 硬编码 URL | 将各组件中的 `http://localhost:5002` 替换为 `apiOrigins.js` 常量，使用 `authFetch` | 无影响，反而修复了端口不一致的潜在 bug |

### 第二阶段：需要配合服务器端一起改

> 这些修改涉及客户端与服务器的通信配置，需要先确保服务器端就绪，再修改客户端。

| 序号 | 对应漏洞 | 具体操作 | 前置条件 | 注意事项 |
|------|---------|---------|---------|---------|
| 5 | #4 CSP 配置 | 在 `tauri.conf.json` 中启用 CSP，把所有实际使用的 API 地址加入白名单 | 梳理所有 `connect-src` 需要的域名和端口 | 白名单遗漏会导致前端请求被拦截，需逐一测试 |
| 6 | #7 CORS 配置 | 将 `CORS_ALLOW_ALL` 默认改为 `false`，配置白名单 | 确认 Tauri 的 Origin 头（`tauri://localhost`）和前端开发地址 | 遗漏 Origin 会导致跨域请求失败 |
| 7 | #9/#10 HTTP 改 HTTPS | 服务器配 SSL 证书后，客户端改为 HTTPS 地址 | **服务器先配好 TLS 证书** | 服务器没配好就改客户端 = 连不上 |
| 8 | #11 Flask 绑定地址 | 将 `0.0.0.0` 改为 `127.0.0.1` | 确认没有跨设备访问的需求（如手机测试、局域网调试） | 如果需要局域网访问，可改为通过防火墙控制而非绑定地址 |
| 9 | #5 任意文件打开 | 在 `sidecar.rs` 中添加扩展名和路径范围验证 | 梳理合法的文件类型和目录范围 | 限制过严会影响导出功能 |
| 10 | #8 Shell 权限 | 将 `shell:allow-execute` 改为 scoped commands | 梳理前端实际需要调用的所有系统命令 | 遗漏命令会导致功能失效 |

### 第三阶段：架构调整（工作量较大，建议单独排期）

> 这些修改涉及认证架构的变动，需要前后端联调，建议在功能稳定后专门排期。

| 序号 | 对应漏洞 | 具体操作 | 注意事项 |
|------|---------|---------|---------|
| 11 | #2 JWT 无签名回退 | 移除 `_extract_supabase_sub_from_bearer` 的回退逻辑，`verify_access_token` 失败直接返回 401 | 需充分测试 Supabase Token 验证流程，确保正常用户在 Token 过期/刷新时不会被误拒 |
| 12 | #6 Token 存储方式 | **过渡方案**：缩短 access_token 有效期至 5-15 分钟，实现 refresh_token rotation。**最终方案**：Tauri 桌面端评估使用 Tauri 安全存储插件替代 localStorage | 改动面广，涉及 AuthContext、apiClient、后端 Token 签发逻辑，需要前后端联调 |