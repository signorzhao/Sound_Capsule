#!/usr/bin/env python3
"""
Sound Capsule 服务管理面板
===========================

统一管理和监控所有服务：
1. Embedding API (端口 8000)
2. Anchor Editor (端口 5001)
3. Capsule API (端口 5000)

功能：
- 一键启动/停止所有服务
- 实时显示服务状态
- 查看服务日志
- 自动检测端口占用
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from datetime import datetime
import threading

try:
    from flask import Flask, render_template_string, jsonify, request
    import psutil
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("警告: Flask 或 psutil 未安装，将使用简化版本")

app = Flask(__name__)

# ==========================================
# 配置
# ==========================================

BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 服务定义
SERVICES = {
    "embedding-api": {
        "name": "Embedding API",
        "description": "云端 Embedding 服务（Phase C2）",
        "port": 8000,
        "script": "embedding_service.py",
        "log_file": LOG_DIR / "embedding_service.log",
        "process_name": "embedding_service.py",
        "required": True,
        "category": "Phase C"
    },
    "anchor-editor": {
        "name": "Anchor Editor",
        "description": "锚点编辑器（Phase C3 集成）",
        "port": 5001,
        "script": "anchor_editor_v2.py",
        "log_file": LOG_DIR / "anchor_editor.log",
        "process_name": "anchor_editor_v2.py",
        "required": True,
        "category": "Core"
    },
    "capsule-api": {
        "name": "Capsule API",
        "description": "胶囊管理 API（核心后端）",
        "port": 5002,
        "script": "capsule_api.py",
        "log_file": LOG_DIR / "capsule_api.log",
        "process_name": "capsule_api.py",
        "required": True,
        "category": "Core"
    }
}

# 存储进程对象
running_processes = {}

# ==========================================
# 工具函数
# ==========================================

def is_port_in_use(port):
    """检查端口是否被占用"""
    try:
        for conn in psutil.net_connections():
            if conn.laddr.port == port:
                return True
        return False
    except:
        # 如果 psutil 不可用，使用备用方法
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

def is_process_running(script_name):
    """检查进程是否正在运行"""
    try:
        found_procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and script_name in ' '.join(cmdline):
                    found_procs.append({
                        'pid': proc.info['pid'],
                        'cpu': proc.info['cpu_percent'],
                        'memory': proc.info['memory_info'].rss
                    })
            except:
                continue
        if found_procs:
            return True, found_procs[0]  # 返回最老的一个
        return False, None
    except:
        return False, None

def force_kill_port(port):
    """暴力杀死占用特定端口的所有进程"""
    killed_count = 0
    killed_pids = []
    
    # 方法1：使用 lsof 查找并终止占用端口的进程（最可靠）
    try:
        import subprocess
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                        killed_count += 1
                        killed_pids.append(int(pid))
                        print(f"✓ 已终止进程 PID {pid} (占用端口 {port})")
                    except ProcessLookupError:
                        print(f"  进程 {pid} 已终止或不存在")
                        continue
                    except PermissionError:
                        print(f"✗ 无权限终止进程 {pid}，请使用 sudo")
                        continue
            
            if killed_count > 0:
                time.sleep(0.5)  # 等待进程完全退出
                return True, f"已清理 {killed_count} 个冲突进程 (PID: {', '.join(map(str, killed_pids))})"
    except FileNotFoundError:
        print("⚠ lsof 命令不可用，尝试使用 psutil")
    except subprocess.TimeoutExpired:
        print("⚠ lsof 命令超时")
    except Exception as e:
        print(f"⚠ lsof 方法失败: {e}")
    
    # 方法2：使用 psutil 遍历进程（备用方案）
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                conns = proc.connections(kind='inet')
                for conn in conns:
                    if conn.laddr.port == port:
                        try:
                            os.kill(proc.pid, signal.SIGKILL)
                            killed_count += 1
                            killed_pids.append(proc.pid)
                            print(f"✓ 已终止进程 PID {proc.pid} (占用端口 {port})")
                            break
                        except psutil.NoSuchProcess:
                            print(f"  进程 {proc.pid} 已终止")
                            continue
                        except psutil.AccessDenied:
                            print(f"✗ 无权限终止进程 {proc.pid}")
                            continue
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except psutil.ZombieProcess:
                continue
            except Exception:
                continue
        
        if killed_count > 0:
            time.sleep(0.5)  # 等待进程完全退出
            return True, f"已清理 {killed_count} 个冲突进程 (PID: {', '.join(map(str, killed_pids))})"
        else:
            return True, f"未发现占用端口 {port} 的进程，端口已可用"
            
    except Exception as e:
        return False, f"清理端口时发生错误: {str(e)}"

def get_service_status(service_id):
    """获取服务状态"""
    service = SERVICES[service_id]

    # 检查端口
    port_in_use = is_port_in_use(service['port'])

    # 检查进程
    is_running, proc_info = is_process_running(service['process_name'])
    pid = proc_info['pid'] if is_running else None
    cpu = proc_info['cpu'] if is_running else 0
    mem = proc_info['memory'] if is_running else 0

    # 检查是否有我们的进程记录
    managed = service_id in running_processes

    # 判断状态
    if is_running and managed:
        status = "running"
        status_text = "运行中"
    elif port_in_use:
        status = "external"
        status_text = "外部占用"
    else:
        status = "stopped"
        status_text = "已停止"

    return {
        "id": service_id,
        "name": service['name'],
        "description": service['description'],
        "port": service['port'],
        "status": status,
        "status_text": status_text,
        "pid": pid,
        "cpu": cpu,
        "memory": mem,
        "required": service['required'],
        "category": service['category'],
        "managed": managed,
        "log_file": str(service['log_file'])
    }

def start_service(service_id):
    """启动服务"""
    if service_id in running_processes:
        return {"success": False, "message": "服务已在运行中"}

    service = SERVICES[service_id]
    script_path = BASE_DIR / service['script']

    if not script_path.exists():
        return {"success": False, "message": f"脚本不存在: {script_path}"}

    try:
        # 打开日志文件
        log_file = open(service['log_file'], 'w')
        log_file.write(f"=== 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        log_file.flush()

        # 启动进程
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=BASE_DIR,
            preexec_fn=os.setsid  # 创建新的进程组
        )

        running_processes[service_id] = {
            'process': process,
            'log_file': log_file,
            'start_time': datetime.now()
        }

        # 等待一下确保启动成功
        time.sleep(2)

        if process.poll() is None:
            return {
                "success": True,
                "message": f"服务启动成功 (PID: {process.pid})",
                "pid": process.pid
            }
        else:
            # 进程已经退出
            del running_processes[service_id]
            log_file.close()
            return {"success": False, "message": "服务启动失败（查看日志）"}

    except Exception as e:
        return {"success": False, "message": f"启动失败: {str(e)}"}

def stop_service(service_id):
    """停止服务"""
    if service_id not in running_processes:
        return {"success": False, "message": "服务未在管理中运行"}

    try:
        proc_info = running_processes[service_id]
        process = proc_info['process']
        log_file = proc_info['log_file']

        # 发送 SIGTERM 到整个进程组
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except:
            process.terminate()

        # 等待进程结束
        try:
            process.wait(timeout=5)
        except:
            # 强制杀死
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except:
                process.kill()

        log_file.write(f"\n=== 停止时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        log_file.close()

        del running_processes[service_id]

        return {"success": True, "message": "服务已停止"}

    except Exception as e:
        return {"success": False, "message": f"停止失败: {str(e)}"}

def get_service_logs(service_id, lines=50):
    """获取服务日志"""
    service = SERVICES[service_id]
    log_file = service['log_file']

    if not log_file.exists():
        return "日志文件不存在"

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            # 返回最后 N 行
            return ''.join(all_lines[-lines:])
    except Exception as e:
        return f"读取日志失败: {str(e)}"

# ==========================================
# HTML 模板
# ==========================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sound Capsule | Command Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0a0e1a;
            --card-bg: rgba(255, 255, 255, 0.05);
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-yellow: #f59e0b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --glass-border: rgba(255, 255, 255, 0.1);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-color);
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.05) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(147, 51, 234, 0.05) 0%, transparent 40%);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 40px 20px;
            overflow-x: hidden;
        }

        .container { max-width: 1400px; margin: 0 auto; }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
            padding: 0 10px;
        }

        .header-title h1 {
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(to right, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 4px;
        }

        .header-title p { color: var(--text-secondary); font-size: 14px; }

        .global-stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .stat-label { color: var(--text-secondary); font-size: 13px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
        .stat-value { font-size: 32px; font-weight: 700; }
        .stat-running { color: var(--accent-green); }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 24px;
        }

        .service-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            padding: 28px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }

        .service-card:hover { transform: translateY(-4px); border-color: rgba(59, 130, 246, 0.4); box-shadow: 0 20px 40px rgba(0,0,0,0.3); }

        .service-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 24px;
        }

        .service-title h3 { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
        .service-title p { color: var(--text-secondary); font-size: 13px; margin-bottom: 12px; }

        .status-pill {
            padding: 6px 14px;
            border-radius: 100px;
            font-size: 12px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .status-pill::before {
            content: '';
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        .status-running { background: rgba(16, 185, 129, 0.1); color: var(--accent-green); }
        .status-running::before { background: var(--accent-green); box-shadow: 0 0 10px var(--accent-green); animation: pulse 2s infinite; }

        .status-stopped { background: rgba(239, 68, 68, 0.1); color: var(--accent-red); }
        .status-stopped::before { background: var(--accent-red); }

        .status-external { background: rgba(245, 158, 11, 0.1); color: var(--accent-yellow); }
        .status-external::before { background: var(--accent-yellow); }

        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }

        .resource-metrics {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 24px;
        }

        .metric-box {
            background: rgba(0, 0, 0, 0.2);
            padding: 12px;
            border-radius: 12px;
            text-align: center;
        }

        .metric-label { font-size: 11px; color: var(--text-secondary); margin-bottom: 4px; }
        .metric-value { font-family: 'JetBrains Mono', monospace; font-size: 14px; color: var(--accent-blue); }

        .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

        .btn {
            padding: 12px;
            border-radius: 10px;
            border: none;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            color: white;
            text-decoration: none;
        }

        .btn-primary { background: var(--accent-blue); }
        .btn-primary:hover { background: #2563eb; }
        .btn-secondary { background: rgba(255, 255, 255, 0.1); }
        .btn-secondary:hover { background: rgba(255, 255, 255, 0.15); }
        .btn-danger { background: rgba(239, 68, 68, 0.15); color: var(--accent-red); border: 1px solid rgba(239, 68, 68, 0.2); }
        .btn-danger:hover { background: rgba(239, 68, 68, 0.25); }

        .btn:disabled { opacity: 0.3; cursor: not-allowed; }

        /* Log Viewer Overlay */
        #log-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(10px);
            z-index: 1000;
            padding: 40px;
        }

        .log-window {
            max-width: 1000px;
            margin: 0 auto;
            background: #000;
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            height: calc(100vh - 80px);
            display: flex;
            flex-direction: column;
            box-shadow: 0 40px 100px rgba(0,0,0,0.5);
        }

        .log-header {
            padding: 20px 24px;
            border-bottom: 1px solid var(--glass-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .log-content {
            flex: 1;
            padding: 24px;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            line-height: 1.6;
            color: #ccc;
            white-space: pre-wrap;
        }

        .log-content::-webkit-scrollbar { width: 8px; }
        .log-content::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }

        .close-logs { font-size: 20px; cursor: pointer; color: var(--text-secondary); transition: color 0.2s; }
        .close-logs:hover { color: white; }

        .floating-notif {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 16px 24px;
            border-radius: 12px;
            background: var(--accent-blue);
            color: white;
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
            transform: translateY(100px);
            transition: all 0.3s ease;
            z-index: 2000;
        }
        .floating-notif.show { transform: translateY(0); }

        .port-occupied-alert {
            margin-top: 15px;
            padding: 12px;
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid rgba(245, 158, 11, 0.2);
            border-radius: 10px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .category-tag {
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            padding: 4px 8px;
            background: rgba(59, 130, 246, 0.1);
            color: var(--accent-blue);
            border-radius: 4px;
            display: inline-block;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-title">
                <h1>Command Center</h1>
                <p>Sound Capsule Service Infrastructure Panel</p>
            </div>
            <div class="actions" style="margin-left: auto;">
                <button class="btn btn-secondary" onclick="startAll()">Launch All</button>
                <button class="btn btn-danger" onclick="stopAll()">Kill All</button>
            </div>
        </div>

        <div class="global-stats">
            <div class="stat-card">
                <span class="stat-label">Active</span>
                <span class="stat-value stat-running" id="active-count">0</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Offline</span>
                <span class="stat-value" id="offline-count">0</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Conflict</span>
                <span class="stat-value" style="color: var(--accent-yellow);" id="conflict-count">0</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">API Status</span>
                <span class="stat-value" id="api-status" style="font-size: 14px; margin-top: 15px;">Operational</span>
            </div>
        </div>

        <div class="grid" id="service-grid">
            <!-- Services injected here -->
        </div>
    </div>

    <div id="log-overlay" onclick="if(event.target==this) closeLogs()">
        <div class="log-window">
            <div class="log-header">
                <h2 id="log-title">Service Logs</h2>
                <div style="display: flex; gap: 15px; align-items: center;">
                    <span id="log-status" style="font-size: 12px; color: var(--text-secondary);">Real-time</span>
                    <span class="close-logs" onclick="closeLogs()">✕</span>
                </div>
            </div>
            <div class="log-content" id="log-body"></div>
        </div>
    </div>

    <div id="toast" class="floating-notif"></div>

    <script>
        let services = [];
        let currentLogId = null;
        let logInterval = null;

        function showToast(msg) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.className = 'floating-notif show';
            setTimeout(() => { toast.className = 'floating-notif'; }, 3000);
        }

        function formatBytes(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        }

        async function updateStatus() {
            try {
                const res = await fetch('/api/services');
                const data = await res.json();
                services = data.services;
                render();
            } catch (err) {
                console.error('Failed to fetch services', err);
            }
        }

        async function serviceAction(id, action) {
            try {
                const res = await fetch(`/api/services/${id}/${action}`, { method: 'POST' });
                const data = await res.json();
                showToast(data.message);
                updateStatus();
            } catch (err) {
                showToast('Action failed');
            }
        }

        async function startAll() {
            const res = await fetch('/api/services/start-all', { method: 'POST' });
            const data = await res.json();
            showToast(data.message);
            updateStatus();
        }

        async function stopAll() {
            const res = await fetch('/api/services/stop-all', { method: 'POST' });
            const data = await res.json();
            showToast(data.message);
            updateStatus();
        }

        function showLogs(id) {
            currentLogId = id;
            document.getElementById('log-overlay').style.display = 'block';
            document.getElementById('log-title').textContent = `Logs: ${id}`;
            fetchLogs();
            if (logInterval) clearInterval(logInterval);
            logInterval = setInterval(fetchLogs, 2000);
        }

        async function fetchLogs() {
            if (!currentLogId) return;
            const res = await fetch(`/api/services/${currentLogId}/logs`);
            const data = await res.json();
            const body = document.getElementById('log-body');
            body.textContent = data.logs || 'No logs found.';
            body.scrollTop = body.scrollHeight;
        }

        function closeLogs() {
            document.getElementById('log-overlay').style.display = 'none';
            currentLogId = null;
            if (logInterval) clearInterval(logInterval);
        }

        function render() {
            const grid = document.getElementById('service-grid');
            let html = '';
            let active = 0, offline = 0, conflict = 0;

            services.forEach(s => {
                if(s.status === 'running') active++;
                else if(s.status === 'external') conflict++;
                else offline++;

                html += `
                <div class="service-card">
                    <div class="service-header">
                        <div class="service-title">
                            <span class="category-tag">${s.category}</span>
                            <h3 style="margin-top: 8px;">${s.name}</h3>
                            <p>${s.description}</p>
                        </div>
                        <div class="status-pill status-${s.status}">${s.status_text}</div>
                    </div>
                    
                    <div class="resource-metrics">
                        <div class="metric-box">
                            <div class="metric-label">CPU</div>
                            <div class="metric-value">${s.cpu.toFixed(1)}%</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Memory</div>
                            <div class="metric-value">${formatBytes(s.memory)}</div>
                        </div>
                    </div>

                    ${s.status === 'external' ? `
                    <div class="port-occupied-alert">
                        <div style="font-size: 12px; color: var(--accent-yellow);">⚠️ Port ${s.port} occupied by non-manager process.</div>
                        <button class="btn btn-danger" style="padding: 6px; font-size: 12px;" onclick="serviceAction('${s.id}', 'fix-port')">
                            Force Clear & Start
                        </button>
                    </div>
                    ` : `
                    <div class="actions" style="margin-top: 20px;">
                        <button class="btn btn-primary" onclick="serviceAction('${s.id}', '${s.status === 'running' ? 'restart' : 'start'}')" ${s.status === 'external' ? 'disabled' : ''}>
                            ${s.status === 'running' ? '↺ Restart' : '▶ Start'}
                        </button>
                        <button class="btn btn-secondary" onclick="showLogs('${s.id}')">
                            📋 Logs
                        </button>
                        ${s.status === 'running' ? `
                            <button class="btn btn-danger" style="grid-column: span 2; margin-top: 8px;" onclick="serviceAction('${s.id}', 'stop')">
                                Stop Process
                            </button>
                        ` : ''}
                    </div>
                    `}
                </div>
                `;
            });

            grid.innerHTML = html;
            document.getElementById('active-count').textContent = active;
            document.getElementById('offline-count').textContent = offline;
            document.getElementById('conflict-count').textContent = conflict;
        }

        setInterval(updateStatus, 3000);
        updateStatus();
    </script>
</body>
</html>
"""

# ==========================================
# API 路由
# ==========================================

@app.route('/')
def index():
    """主页"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/services')
def get_services():
    """获取所有服务状态"""
    services = []
    for service_id in SERVICES:
        services.append(get_service_status(service_id))
    return jsonify({"services": services})

@app.route('/api/services/<service_id>/start', methods=['POST'])
def start_service_api(service_id):
    """启动服务"""
    if service_id not in SERVICES:
        return jsonify({"success": False, "message": "服务不存在"})
    return jsonify(start_service(service_id))

@app.route('/api/services/<service_id>/stop', methods=['POST'])
def stop_service_api(service_id):
    """停止服务"""
    if service_id not in SERVICES:
        return jsonify({"success": False, "message": "服务不存在"})
    return jsonify(stop_service(service_id))

@app.route('/api/services/<service_id>/restart', methods=['POST'])
def restart_service_api(service_id):
    """重启服务"""
    if service_id not in SERVICES:
        return jsonify({"success": False, "message": "服务不存在"})
    
    # 停止
    if service_id in running_processes:
        stop_service(service_id)
        time.sleep(1)
        
    # 启动
    return jsonify(start_service(service_id))

@app.route('/api/services/<service_id>/fix-port', methods=['POST'])
def fix_port_api(service_id):
    """强行清理端口占用并启动服务"""
    if service_id not in SERVICES:
        return jsonify({"success": False, "message": "服务不存在"})
    
    service = SERVICES[service_id]
    success, message = force_kill_port(service['port'])
    
    if success:
        time.sleep(1)
        return jsonify(start_service(service_id))
    else:
        return jsonify({"success": False, "message": f"清理失败: {message}"})

@app.route('/api/services/<service_id>/force-kill', methods=['POST'])
def force_kill_api(service_id):
    """强行杀死该服务的相关进程"""
    if service_id not in SERVICES:
        return jsonify({"success": False, "message": "服务不存在"})
    
    service = SERVICES[service_id]
    success, message = force_kill_port(service['port'])
    
    # 同时尝试杀掉匹配脚本名的进程
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if any(service['process_name'] in arg for arg in (proc.info['cmdline'] or [])):
                proc.kill()
    except:
        pass

    return jsonify({"success": success, "message": message})

@app.route('/api/services/start-all', methods=['POST'])
def start_all_services():
    """启动所有必需的服务"""
    success_count = 0
    failed_services = []

    for service_id, service in SERVICES.items():
        if service['required']:
            result = start_service(service_id)
            if result['success']:
                success_count += 1
            else:
                failed_services.append(service['name'])

    if failed_services:
        return jsonify({
            "success": False,
            "message": f"部分服务启动失败: {', '.join(failed_services)}"
        })
    else:
        return jsonify({
            "success": True,
            "message": f"成功启动 {success_count} 个服务"
        })

@app.route('/api/services/stop-all', methods=['POST'])
def stop_all_services():
    """停止所有服务"""
    stopped_count = 0
    for service_id in list(running_processes.keys()):
        result = stop_service(service_id)
        if result['success']:
            stopped_count += 1

    return jsonify({
        "success": True,
        "message": f"已停止 {stopped_count} 个服务"
    })

@app.route('/api/services/<service_id>/logs')
def get_service_logs_api(service_id):
    """获取服务日志"""
    if service_id not in SERVICES:
        return jsonify({"success": False, "logs": "服务不存在"})

    logs = get_service_logs(service_id)
    return jsonify({"success": True, "logs": logs})

# ==========================================
# 清理函数
# ==========================================

def cleanup():
    """清理所有进程"""
    for service_id in list(running_processes.keys()):
        try:
            stop_service(service_id)
        except:
            pass

# ==========================================
# 主程序
# ==========================================

if __name__ == '__main__':
    print("=" * 60)
    print("🎛️  Sound Capsule 服务管理面板")
    print("=" * 60)
    print()

    if not FLASK_AVAILABLE:
        print("❌ Flask 未安装，请运行: pip install flask psutil")
        sys.exit(1)

    print(f"📁 工作目录: {BASE_DIR}")
    print(f"📋 日志目录: {LOG_DIR}")
    print()
    print("📋 已注册服务:")
    for service_id, service in SERVICES.items():
        print(f"   - {service['name']} (端口: {service['port']})")
        print(f"     {service['description']}")
    print()

    # 启动服务器
    port = 5900
    print(f"🚀 启动服务管理面板...")
    print(f"   访问地址: http://localhost:{port}")
    print()
    print("功能:")
    print("   ✅ 一键启动/停止所有服务")
    print("   ✅ 实时查看服务状态")
    print("   ✅ 查看服务日志")
    print("   ✅ 自动检测端口占用")
    print()
    print("=" * 60)
    print()

    try:
        app.run(host='0.0.0.0', port=port, debug=False)
    finally:
        cleanup()
        print("👋 所有服务已停止")
