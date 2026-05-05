# Sound Capsule LAN

仅在 **可信局域网** 内使用的胶囊点对点收发工具。从同仓库的 `synesth` 项目精简而来：

- **不依赖** Supabase / 任何云服务
- **不需要** 用户登录 / JWT
- 只保留：**本地胶囊库**、**生成 / 导入胶囊**、**向指定 IP 发送**、**接收他人胶囊到本机**

> 原 `synesth` 项目保持完整，包含云同步、登录、Reaper 全套捕获等能力。

---

## 项目结构

```
lan-capsule/
├── server/                 # Python Flask 服务
│   ├── app.py              # 入口
│   ├── db.py               # SQLite 访问层
│   ├── schema.sql          # 表结构（capsules / contacts / transfers）
│   ├── bundle.py           # 胶囊打包 / 解包（zip）
│   ├── net.py              # 本机网络信息
│   ├── requirements.txt
│   └── data/               # 运行时生成（数据库 + 胶囊文件）
├── webapp/                 # Vite + React + Tailwind 前端
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   └── components/
│   └── package.json
└── scripts/
    ├── start_server.sh
    └── start_webapp.sh
```

## 快速开始

### 1. 启动后端

```bash
cd lan-capsule
bash scripts/start_server.sh   # 默认 http://0.0.0.0:5005
```

首次会自动创建 `.venv` 并安装 `Flask / flask-cors / requests`。

### 2. 启动前端

```bash
bash scripts/start_webapp.sh   # 默认 http://localhost:3100
```

首次会执行 `npm install`。前端在顶栏显示 **本机名称 · IP:端口**，把这串告诉对方即可。

### 3. 双机收发

1. **A 机**：在“库”页点击 **导入胶囊** 上传一个 `.capsule.zip`，或后续接通 Reaper 的导出流程。
2. **A 机**：进入“发送”页 → 选目标（联系人 / 临时 IP） → 选胶囊 → **立即发送**。
3. **B 机**：胶囊会出现在“库”页，并标注 **来自 …**。

## 主要 API

| Method | Path                          | 说明                         |
| ------ | ----------------------------- | ---------------------------- |
| GET    | `/api/health`                 | 健康检查                     |
| GET    | `/api/network/info`           | 本机 IP / 端口 / 主机名      |
| GET    | `/api/capsules`               | 胶囊列表                     |
| POST   | `/api/capsules`               | 创建胶囊（zip 或 source_dir）|
| DELETE | `/api/capsules/:id`           | 删除胶囊（含文件）           |
| GET    | `/api/capsules/:id/bundle`    | 下载该胶囊的 zip 包          |
| GET    | `/api/contacts`               | 联系人列表                   |
| POST   | `/api/contacts`               | 添加 / 更新联系人            |
| POST   | `/api/contacts/ping`          | 探测某 IP:端口在线           |
| POST   | `/api/p2p/send`               | 发送本地胶囊给指定 IP        |
| POST   | `/api/p2p/import`             | （对方调用）接收胶囊         |
| GET    | `/api/transfers`              | 收发历史                     |

## 安全提示

- **仅在你信任的局域网中运行**；服务默认监听 `0.0.0.0`。
- 可在 `.env` 设置 `LAN_CAPSULE_SHARED_TOKEN`：发送方与接收方需带相同 `X-Capsule-Token` 请求头才能完成接收。
- 系统防火墙可能需要放行后端端口（默认 `5005`）。

## 与原 `synesth` 项目的关系

- 后端不再加载 `cloud_routes` / `supabase_client` / `auth`；数据库为新建的精简表，与原 `capsules.db` **互不兼容**。
- 前端从你提供的 React 原型出发，移除了登录 / 云同步路由；UI 风格沿用 `slate / indigo` 暗色调。
- 后续若想把已有胶囊迁过来，可写一个一次性脚本：从 `synesth/data-pipeline/capsule_db.py` 导出 → 调用本项目 `/api/capsules` 上传。
