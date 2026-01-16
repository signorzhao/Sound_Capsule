#!/usr/bin/env python3
"""
锚点编辑器 - Anchor Editor
===========================
用于编辑棱镜锚点描述、重构数据、验证分布的 Web 工具

功能：
1. 编辑各棱镜的锚点描述词
2. 重新生成向量数据
3. 验证数据分布合理性
4. 可视化四象限分布

启动方式：
    python anchor_editor.py
    
然后访问 http://localhost:5001
"""

import json
import os
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify
import numpy as np

# 尝试导入 ML 库
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("警告: sentence-transformers 未安装，部分功能不可用")

app = Flask(__name__)

# 路径配置
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "anchor_config.json"
OUTPUT_FILE = BASE_DIR.parent / "webapp" / "public" / "data" / "sonic_vectors.json"

# 默认锚点配置
DEFAULT_CONFIG = {
    "texture": {
        "name": "Texture / Timbre (质感)",
        "description": "声音的质感和情绪色彩",
        "lexicon_file": "lexicon_texture.csv",
        "axes": {
            "x_label": {"neg": "Dark / 黑暗恐惧", "pos": "Light / 光明治愈"},
            "y_label": {"neg": "Realistic / 写实严肃", "pos": "Playful / 趣味活跃"}
        },
        "axis_x_neg": "dark horror scary fear terror nightmare death blood murder crime violence war destruction pain suffering torture evil demon monster ghost sinister menacing threatening dangerous",
        "axis_x_pos": "light bright beautiful lovely peaceful serene tranquil calm soothing healing therapeutic pure clean fresh gentle soft warm comforting relaxing meditation zen spiritual divine sacred holy angelic heaven",
        "axis_y_neg": "realistic serious dramatic cinematic documentary film movie authentic genuine raw organic natural acoustic real professional studio high-fidelity serious tense suspense thriller",
        "axis_y_pos": "playful fun cartoon game arcade toy child kid cute adorable silly goofy funny comic humorous whimsical bouncy springy bubble candy sweet colorful rainbow magical fantasy fairy unicorn nintendo 8-bit retro pixel"
    },
    "source": {
        "name": "Source & Physics (源场)",
        "description": "声音的物理特征与来源属性",
        "lexicon_file": "lexicon_source.csv",
        "axes": {
            "x_label": {"neg": "Static / 静态铺底", "pos": "Transient / 瞬态冲击"},
            "y_label": {"neg": "Organic / 有机自然", "pos": "Sci-Fi / 科幻合成"}
        },
        "axis_x_neg": "static drone pad ambient sustained continuous endless loop humming droning steady constant background bed layer texture atmosphere evolving",
        "axis_x_pos": "transient impact hit punch attack burst snap crack pop click bang boom smash crash instant sudden sharp percussive one-shot",
        "axis_y_neg": "organic natural real acoustic foley field-recording authentic earthy wooden animal human nature creature wildlife bird insect water wind fire rain forest",
        "axis_y_pos": "synthetic digital electronic sci-fi futuristic robotic mechanical artificial processed cyber tech laser plasma energy beam glitch data computer spaceship robot"
    },
    "materiality": {
        "name": "Materiality / Room (材质)",
        "description": "声音的空间材质与距离特征",
        "lexicon_file": "lexicon_materiality.csv",
        "axes": {
            "x_label": {"neg": "Close / 贴耳干涩", "pos": "Distant / 遥远湿润"},
            "y_label": {"neg": "Cold / 冷硬反射", "pos": "Warm / 暖软吸音"}
        },
        "axis_x_neg": "close proximity near intimate whisper ear direct dry anechoic booth studio recording isolation upfront present focused tight small-room confined no-reverb dead-room",
        "axis_x_pos": "distant far away reverb reverberation echo long-reverb hall cathedral canyon cave vast spacious open wide diffused atmospheric immersive long-tail large-space stadium arena",
        "axis_y_neg": "cold frozen ice metallic metal glass tile ceramic steel concrete stone marble clinical surgical sterile industrial reflective hard bright harsh sharp ringing high-frequency tinny bathroom hospital",
        "axis_y_pos": "warm cozy soft fabric blanket carpet wood wooden cabin forest cloth cotton velvet muffled muted dull dampened absorbed absorptive low-frequency bass underwater mud muddy dark bedroom living-room"
    }
}

# HTML 模板
HTML_TEMPLATE = r'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>锚点编辑器 - Anchor Editor</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0f; 
            color: #e0e0e0; 
            padding: 20px;
            line-height: 1.6;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { 
            font-size: 24px; 
            margin-bottom: 20px; 
            color: #fff;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        h1 span { font-size: 12px; color: #666; font-weight: normal; }
        
        .tabs { 
            display: flex; 
            gap: 5px; 
            margin-bottom: 20px; 
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
        }
        .tab { 
            padding: 10px 20px; 
            background: #1a1a2e; 
            border: 1px solid #333;
            border-radius: 8px 8px 0 0;
            cursor: pointer;
            color: #888;
            transition: all 0.2s;
        }
        .tab:hover { background: #252540; color: #fff; }
        .tab.active { 
            background: #2a2a4e; 
            color: #fff; 
            border-color: #6366f1;
        }
        
        .panel { display: none; }
        .panel.active { display: block; }
        
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        
        .card {
            background: #12121a;
            border: 1px solid #2a2a3e;
            border-radius: 12px;
            padding: 20px;
        }
        .card h3 { 
            font-size: 14px; 
            color: #888; 
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .card h3 .label {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            margin-left: 8px;
        }
        .card h3 .label.neg { background: #3b1d1d; color: #f87171; }
        .card h3 .label.pos { background: #1d3b2a; color: #4ade80; }
        
        textarea {
            width: 100%;
            min-height: 120px;
            background: #0a0a10;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 12px;
            color: #e0e0e0;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 13px;
            resize: vertical;
        }
        textarea:focus { outline: none; border-color: #6366f1; }
        
        .word-count {
            font-size: 11px;
            color: #666;
            margin-top: 5px;
            text-align: right;
        }
        
        .actions {
            display: flex;
            gap: 10px;
            margin-top: 20px;
            flex-wrap: wrap;
        }
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s;
        }
        .btn-primary { background: #6366f1; color: #fff; }
        .btn-primary:hover { background: #5558e3; }
        .btn-secondary { background: #2a2a3e; color: #e0e0e0; }
        .btn-secondary:hover { background: #3a3a4e; }
        .btn-danger { background: #dc2626; color: #fff; }
        .btn-danger:hover { background: #b91c1c; }
        
        .status {
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            display: none;
        }
        .status.show { display: block; }
        .status.success { background: #1d3b2a; border: 1px solid #4ade80; }
        .status.error { background: #3b1d1d; border: 1px solid #f87171; }
        .status.info { background: #1d2d3b; border: 1px solid #60a5fa; }
        
        .validation {
            margin-top: 20px;
            background: #12121a;
            border: 1px solid #2a2a3e;
            border-radius: 12px;
            padding: 20px;
        }
        .validation h3 { margin-bottom: 15px; }
        .quadrant-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .quadrant {
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        }
        .quadrant.tl { background: #2d1f3d; border: 1px solid #8b5cf6; }
        .quadrant.tr { background: #1f2d3d; border: 1px solid #3b82f6; }
        .quadrant.bl { background: #3d2d1f; border: 1px solid #f59e0b; }
        .quadrant.br { background: #1f3d2d; border: 1px solid #10b981; }
        .quadrant h4 { font-size: 12px; margin-bottom: 8px; opacity: 0.8; }
        .quadrant .count { font-size: 24px; font-weight: bold; }
        .quadrant .samples { font-size: 11px; opacity: 0.7; margin-top: 5px; }
        
        .loading { 
            display: inline-block; 
            width: 16px; 
            height: 16px; 
            border: 2px solid #fff; 
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 8px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .ml-warning {
            background: #3b2d1f;
            border: 1px solid #f59e0b;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        
        /* 模态框样式 */
        .modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        .modal-content {
            background: #12121a;
            border: 1px solid #333;
            border-radius: 16px;
            padding: 30px;
            max-width: 700px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
        }
        .modal-content h2 {
            margin-bottom: 20px;
            font-size: 20px;
        }
        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        .form-group.full-width {
            grid-column: 1 / -1;
        }
        .form-group label {
            font-size: 12px;
            color: #888;
        }
        .form-group input, .form-group textarea {
            background: #0a0a10;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 10px;
            color: #e0e0e0;
            font-size: 13px;
        }
        .form-group input:focus, .form-group textarea:focus {
            outline: none;
            border-color: #6366f1;
        }
        .modal-actions {
            display: flex;
            gap: 10px;
            margin-top: 20px;
            justify-content: flex-end;
        }
        
        /* 未激活棱镜样式 */
        .tab.inactive-lens {
            opacity: 0.5;
            border-style: dashed;
        }
        .toggle-label {
            font-size: 12px;
            color: #888;
        }
        .toggle-label input {
            width: 16px;
            height: 16px;
            cursor: pointer;
        }
        .btn-danger {
            background: #7f1d1d;
            color: #fca5a5;
        }
        .btn-danger:hover {
            background: #991b1b;
        }
        
        /* 日志区域样式 */
        .log-container {
            margin-top: 30px;
            background: #0a0a10;
            border: 1px solid #2a2a3e;
            border-radius: 12px;
            overflow: hidden;
        }
        .log-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 15px;
            background: #12121a;
            border-bottom: 1px solid #2a2a3e;
        }
        .log-header h3 {
            font-size: 13px;
            color: #888;
            margin: 0;
        }
        .log-content {
            max-height: 200px;
            overflow-y: auto;
            padding: 10px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 11px;
        }
        .log-entry {
            padding: 4px 8px;
            margin: 2px 0;
            border-radius: 4px;
            display: flex;
            gap: 8px;
        }
        .log-entry .time {
            color: #666;
            flex-shrink: 0;
        }
        .log-entry .msg {
            word-break: break-all;
        }
        .log-entry.success { background: #0d2818; color: #4ade80; }
        .log-entry.error { background: #2d1212; color: #f87171; }
        .log-entry.info { background: #12182d; color: #60a5fa; }
        .log-entry.warning { background: #2d2412; color: #fbbf24; }
    </style>
</head>
<body>
    <div class="container">
        <h1>
            🎛️ 锚点编辑器 <span>Anchor Editor v1.0</span>
        </h1>
        
        {% if not ml_available %}
        <div class="ml-warning">
            ⚠️ sentence-transformers 未安装，无法重构数据。请运行: <code>pip install sentence-transformers</code>
        </div>
        {% endif %}
        
        <div class="tabs">
            {% for key, lens in config.items() %}
            <div class="tab {% if loop.first %}active{% endif %} {% if not lens.get('active', true) %}inactive-lens{% endif %}" data-lens="{{ key }}">
                {% if lens.get('active', true) %}🟢{% else %}⚫{% endif %} {{ lens.name }}
            </div>
            {% endfor %}
            <div class="tab" style="background: #1a3d1a; border-color: #4ade80;" onclick="showNewLensModal()">
                ➕ 新建棱镜
            </div>
        </div>
        
        <!-- 新建棱镜模态框 -->
        <div id="newLensModal" class="modal" style="display: none;">
            <div class="modal-content">
                <h2>🆕 新建棱镜</h2>
                <div class="form-grid">
                    <div class="form-group">
                        <label>棱镜 ID（英文标识，如 emotion）</label>
                        <input type="text" id="newLensId" placeholder="emotion">
                    </div>
                    <div class="form-group">
                        <label>棱镜名称（如 Emotion / 情感）</label>
                        <input type="text" id="newLensName" placeholder="Emotion / 情感 (情绪)">
                    </div>
                    <div class="form-group full-width">
                        <label>棱镜描述</label>
                        <input type="text" id="newLensDesc" placeholder="声音的情绪色彩与能量">
                    </div>
                    <div class="form-group">
                        <label>X轴负向标签</label>
                        <input type="text" id="newLensXNegLabel" placeholder="Sad / 悲伤">
                    </div>
                    <div class="form-group">
                        <label>X轴正向标签</label>
                        <input type="text" id="newLensXPosLabel" placeholder="Happy / 欢乐">
                    </div>
                    <div class="form-group">
                        <label>Y轴负向标签</label>
                        <input type="text" id="newLensYNegLabel" placeholder="Calm / 平静">
                    </div>
                    <div class="form-group">
                        <label>Y轴正向标签</label>
                        <input type="text" id="newLensYPosLabel" placeholder="Intense / 激烈">
                    </div>
                    <div class="form-group full-width">
                        <label>X轴负向锚点词</label>
                        <textarea id="newLensXNeg" rows="2" placeholder="sad melancholy depressing gloomy dark..."></textarea>
                    </div>
                    <div class="form-group full-width">
                        <label>X轴正向锚点词</label>
                        <textarea id="newLensXPos" rows="2" placeholder="happy joyful cheerful bright uplifting..."></textarea>
                    </div>
                    <div class="form-group full-width">
                        <label>Y轴负向锚点词</label>
                        <textarea id="newLensYNeg" rows="2" placeholder="calm peaceful relaxed serene tranquil..."></textarea>
                    </div>
                    <div class="form-group full-width">
                        <label>Y轴正向锚点词</label>
                        <textarea id="newLensYPos" rows="2" placeholder="intense aggressive energetic powerful driving..."></textarea>
                    </div>
                </div>
                <div class="modal-actions">
                    <button class="btn-primary" onclick="createNewLens()">✅ 创建棱镜</button>
                    <button class="btn-secondary" onclick="hideNewLensModal()">❌ 取消</button>
                </div>
            </div>
        </div>
        
        {% for key, lens in config.items() %}
        <div class="panel {% if loop.first %}active{% endif %}" id="panel-{{ key }}">
            <div class="grid">
                <div class="card">
                    <h3>X轴负向 <span class="label neg">{{ lens.axes.x_label.neg }}</span></h3>
                    <textarea id="{{ key }}_x_neg">{{ lens.axis_x_neg }}</textarea>
                    <div class="word-count" id="{{ key }}_x_neg_count"></div>
                </div>
                <div class="card">
                    <h3>X轴正向 <span class="label pos">{{ lens.axes.x_label.pos }}</span></h3>
                    <textarea id="{{ key }}_x_pos">{{ lens.axis_x_pos }}</textarea>
                    <div class="word-count" id="{{ key }}_x_pos_count"></div>
                </div>
                <div class="card">
                    <h3>Y轴负向 <span class="label neg">{{ lens.axes.y_label.neg }}</span></h3>
                    <textarea id="{{ key }}_y_neg">{{ lens.axis_y_neg }}</textarea>
                    <div class="word-count" id="{{ key }}_y_neg_count"></div>
                </div>
                <div class="card">
                    <h3>Y轴正向 <span class="label pos">{{ lens.axes.y_label.pos }}</span></h3>
                    <textarea id="{{ key }}_y_pos">{{ lens.axis_y_pos }}</textarea>
                    <div class="word-count" id="{{ key }}_y_pos_count"></div>
                </div>
            </div>
            
            <div class="actions">
                <button class="btn-primary" onclick="saveAndRebuild('{{ key }}')">
                    💾 保存并重构此棱镜
                </button>
                <button class="btn-secondary" onclick="validateLens('{{ key }}', true)">
                    🔍 验证分布
                </button>
                <button class="btn-secondary" onclick="resetLens('{{ key }}')">
                    ↩️ 重置为默认
                </button>
                <label class="toggle-label" style="display: flex; align-items: center; gap: 8px; margin-left: auto; cursor: pointer;">
                    <input type="checkbox" id="active-{{ key }}" {% if lens.get('active', true) %}checked{% endif %} onchange="toggleLensActive('{{ key }}')">
                    <span>在主界面显示</span>
                </label>
                {% if key not in ['texture', 'source', 'materiality'] %}
                <button class="btn-danger" onclick="deleteLens('{{ key }}')" style="margin-left: 10px;">
                    🗑️ 删除
                </button>
                {% endif %}
            </div>
            
            <div class="validation" id="validation-{{ key }}" style="display: none;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <h3 style="margin: 0;">📊 四象限分布验证</h3>
                    <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: #888; cursor: pointer;">
                        <input type="checkbox" id="showHint-{{ key }}" onchange="toggleHintDisplay('{{ key }}')" style="cursor: pointer;">
                        显示语义后缀
                    </label>
                </div>
                <div class="quadrant-grid" id="quadrants-{{ key }}"></div>
            </div>
        </div>
        {% endfor %}
        
        <div class="actions" style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #333;">
            <button class="btn-primary" onclick="saveAndRebuildActive()">
                🚀 保存并重构所有激活棱镜
            </button>
            <button class="btn-secondary" onclick="exportConfig()">
                📤 导出配置
            </button>
            <button class="btn-secondary" onclick="importConfig()">
                📥 导入配置
            </button>
        </div>
        
        <div class="status" id="status"></div>
        
        <!-- 日志区域 -->
        <div class="log-container">
            <div class="log-header">
                <h3>📋 操作日志</h3>
                <button class="btn-secondary" onclick="clearLog()" style="padding: 5px 10px; font-size: 11px;">
                    🗑️ 清除
                </button>
            </div>
            <div class="log-content" id="logContent">
                <div class="log-entry info">[启动] 锚点编辑器已加载</div>
            </div>
        </div>
    </div>
    
    <script>
        // Tab 切换
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById('panel-' + tab.dataset.lens).classList.add('active');
            });
        });
        
        // 词数统计
        function updateWordCount(id) {
            const textarea = document.getElementById(id);
            const countEl = document.getElementById(id + '_count');
            if (textarea && countEl) {
                const words = textarea.value.trim().split(/\s+/).filter(w => w.length > 0);
                countEl.textContent = words.length + ' 个词';
            }
        }
        
        document.querySelectorAll('textarea').forEach(ta => {
            updateWordCount(ta.id);
            ta.addEventListener('input', () => updateWordCount(ta.id));
        });
        
        // 显示状态
        function showStatus(message, type) {
            const status = document.getElementById('status');
            status.className = 'status show ' + type;
            status.innerHTML = message;
            if (type !== 'info') {
                setTimeout(() => status.classList.remove('show'), 5000);
            }
            
            // 同时添加到日志（去掉 HTML 标签）
            const cleanMessage = message.replace(/<[^>]*>/g, '').trim();
            if (cleanMessage) {
                addLog(cleanMessage, type);
            }
        }
        
        // 添加日志条目
        function addLog(message, type = 'info') {
            const logContent = document.getElementById('logContent');
            const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
            
            const entry = document.createElement('div');
            entry.className = 'log-entry ' + type;
            entry.innerHTML = `<span class="time">[${time}]</span><span class="msg">${message}</span>`;
            
            logContent.appendChild(entry);
            
            // 滚动到底部
            logContent.scrollTop = logContent.scrollHeight;
            
            // 限制日志条目数量（最多100条）
            while (logContent.children.length > 100) {
                logContent.removeChild(logContent.firstChild);
            }
        }
        
        // 清除日志
        function clearLog() {
            const logContent = document.getElementById('logContent');
            logContent.innerHTML = '<div class="log-entry info"><span class="time">[' + new Date().toLocaleTimeString('zh-CN', { hour12: false }) + ']</span><span class="msg">日志已清除</span></div>';
        }
        
        // 格式化样本显示（双语 + 可选语义后缀）
        function formatSamples(samples, showHint) {
            return samples.map(s => {
                let text = s.cn + ' (' + s.en + ')';
                if (showHint && s.hint) {
                    text += ' <span style="color:#666;font-size:10px;">[' + s.hint + ']</span>';
                }
                return text;
            }).join('<br>');
        }
        
        // 切换语义后缀显示
        function toggleHintDisplay(lens) {
            const data = window['validationData_' + lens];
            if (!data) return;
            
            const showHint = document.getElementById('showHint-' + lens).checked;
            const container = document.getElementById('quadrants-' + lens);
            const quadrants = data.quadrants;
            const total = data.total;
            
            container.innerHTML = `
                <div class="quadrant tl">
                    <h4>左上 ${data.labels.tl}</h4>
                    <div class="count">${quadrants.tl.count} 词 <small>(${Math.round(quadrants.tl.count/total*100)}%)</small></div>
                    <div class="samples">${formatSamples(quadrants.tl.samples, showHint)}</div>
                </div>
                <div class="quadrant tr">
                    <h4>右上 ${data.labels.tr}</h4>
                    <div class="count">${quadrants.tr.count} 词 <small>(${Math.round(quadrants.tr.count/total*100)}%)</small></div>
                    <div class="samples">${formatSamples(quadrants.tr.samples, showHint)}</div>
                </div>
                <div class="quadrant bl">
                    <h4>左下 ${data.labels.bl}</h4>
                    <div class="count">${quadrants.bl.count} 词 <small>(${Math.round(quadrants.bl.count/total*100)}%)</small></div>
                    <div class="samples">${formatSamples(quadrants.bl.samples, showHint)}</div>
                </div>
                <div class="quadrant br">
                    <h4>右下 ${data.labels.br}</h4>
                    <div class="count">${quadrants.br.count} 词 <small>(${Math.round(quadrants.br.count/total*100)}%)</small></div>
                    <div class="samples">${formatSamples(quadrants.br.samples, showHint)}</div>
                </div>
            `;
        }
        
        // 获取锚点数据
        function getAnchorData(lens) {
            return {
                axis_x_neg: document.getElementById(lens + '_x_neg').value,
                axis_x_pos: document.getElementById(lens + '_x_pos').value,
                axis_y_neg: document.getElementById(lens + '_y_neg').value,
                axis_y_pos: document.getElementById(lens + '_y_pos').value
            };
        }
        
        // 保存并重构单个棱镜
        async function saveAndRebuild(lens) {
            showStatus('<span class="loading"></span>正在重构 ' + lens + ' 棱镜...', 'info');
            
            try {
                const response = await fetch('/rebuild', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        lens: lens,
                        anchors: getAnchorData(lens)
                    })
                });
                
                const result = await response.json();
                if (result.success) {
                    showStatus('✅ ' + result.message, 'success');
                    validateLens(lens);
                } else {
                    showStatus('❌ ' + result.message, 'error');
                }
            } catch (e) {
                showStatus('❌ 请求失败: ' + e.message, 'error');
            }
        }
        
        // 保存并重构所有激活的棱镜
        async function saveAndRebuildActive() {
            showStatus('<span class="loading"></span>正在重构所有激活棱镜...', 'info');
            
            // 获取所有激活的棱镜
            const activeLenses = [];
            document.querySelectorAll('.tab[data-lens]').forEach(tab => {
                const lens = tab.dataset.lens;
                const checkbox = document.getElementById('active-' + lens);
                if (lens && checkbox && checkbox.checked) {
                    activeLenses.push(lens);
                }
            });
            
            if (activeLenses.length === 0) {
                showStatus('⚠️ 没有激活的棱镜', 'error');
                return;
            }
            
            const allAnchors = {};
            activeLenses.forEach(lens => {
                allAnchors[lens] = getAnchorData(lens);
            });
            
            try {
                const response = await fetch('/rebuild_all', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(allAnchors)
                });
                
                const result = await response.json();
                if (result.success) {
                    showStatus('✅ ' + result.message, 'success');
                    activeLenses.forEach(lens => validateLens(lens));
                } else {
                    showStatus('❌ ' + result.message, 'error');
                }
            } catch (e) {
                showStatus('❌ 请求失败: ' + e.message, 'error');
            }
        }
        
        // 验证分布
        async function validateLens(lens, scrollTo = false) {
            showStatus('<span class="loading"></span>正在验证 ' + lens + ' 分布...', 'info');
            
            try {
                const response = await fetch('/validate/' + lens);
                const result = await response.json();
                
                if (result.success) {
                    const container = document.getElementById('quadrants-' + lens);
                    const validation = document.getElementById('validation-' + lens);
                    validation.style.display = 'block';
                    
                    const quadrants = result.quadrants;
                    const total = result.total;
                    const showHint = document.getElementById('showHint-' + lens)?.checked || false;
                    
                    // 存储原始数据供切换显示用
                    window['validationData_' + lens] = result;
                    
                    container.innerHTML = `
                        <div class="quadrant tl">
                            <h4>左上 ${result.labels.tl}</h4>
                            <div class="count">${quadrants.tl.count} 词 <small>(${Math.round(quadrants.tl.count/total*100)}%)</small></div>
                            <div class="samples">${formatSamples(quadrants.tl.samples, showHint)}</div>
                        </div>
                        <div class="quadrant tr">
                            <h4>右上 ${result.labels.tr}</h4>
                            <div class="count">${quadrants.tr.count} 词 <small>(${Math.round(quadrants.tr.count/total*100)}%)</small></div>
                            <div class="samples">${formatSamples(quadrants.tr.samples, showHint)}</div>
                        </div>
                        <div class="quadrant bl">
                            <h4>左下 ${result.labels.bl}</h4>
                            <div class="count">${quadrants.bl.count} 词 <small>(${Math.round(quadrants.bl.count/total*100)}%)</small></div>
                            <div class="samples">${formatSamples(quadrants.bl.samples, showHint)}</div>
                        </div>
                        <div class="quadrant br">
                            <h4>右下 ${result.labels.br}</h4>
                            <div class="count">${quadrants.br.count} 词 <small>(${Math.round(quadrants.br.count/total*100)}%)</small></div>
                            <div class="samples">${formatSamples(quadrants.br.samples, showHint)}</div>
                        </div>
                    `;
                    
                    showStatus('✅ 验证完成！共 ' + total + ' 个词汇', 'success');
                    
                    // 滚动到验证区域
                    if (scrollTo) {
                        validation.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                } else {
                    showStatus('❌ 验证失败: 无数据', 'error');
                }
            } catch (e) {
                console.error('验证失败:', e);
                showStatus('❌ 验证请求失败: ' + e.message, 'error');
            }
        }
        
        // 重置为默认
        async function resetLens(lens) {
            if (!confirm('确定要重置 ' + lens + ' 棱镜的锚点为默认值吗？')) return;
            
            try {
                const response = await fetch('/reset/' + lens, { method: 'POST' });
                const result = await response.json();
                if (result.success) {
                    location.reload();
                }
            } catch (e) {
                showStatus('❌ 重置失败: ' + e.message, 'error');
            }
        }
        
        // 导出配置
        function exportConfig() {
            const lenses = ['texture', 'source', 'materiality'];
            const config = {};
            lenses.forEach(lens => {
                config[lens] = getAnchorData(lens);
            });
            
            const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'anchor_config.json';
            a.click();
        }
        
        // 导入配置
        function importConfig() {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = '.json';
            input.onchange = async (e) => {
                const file = e.target.files[0];
                const text = await file.text();
                try {
                    const config = JSON.parse(text);
                    Object.keys(config).forEach(lens => {
                        const anchors = config[lens];
                        Object.keys(anchors).forEach(key => {
                            const el = document.getElementById(lens + '_' + key.replace('axis_', ''));
                            if (el) el.value = anchors[key];
                        });
                    });
                    showStatus('✅ 配置已导入，请点击"保存并重构"应用更改', 'success');
                } catch (e) {
                    showStatus('❌ 导入失败: ' + e.message, 'error');
                }
            };
            input.click();
        }
        
        // ========== 棱镜激活/禁用/删除功能 ==========
        async function toggleLensActive(lens) {
            const isActive = document.getElementById('active-' + lens).checked;
            
            try {
                const response = await fetch('/toggle_active/' + lens, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ active: isActive })
                });
                
                const result = await response.json();
                if (result.success) {
                    showStatus('✅ ' + result.message, 'success');
                    // 更新 Tab 样式
                    const tab = document.querySelector('.tab[data-lens="' + lens + '"]');
                    if (isActive) {
                        tab.classList.remove('inactive-lens');
                        tab.innerHTML = '🟢 ' + tab.textContent.replace('🟢 ', '').replace('⚫ ', '').trim();
                    } else {
                        tab.classList.add('inactive-lens');
                        tab.innerHTML = '⚫ ' + tab.textContent.replace('🟢 ', '').replace('⚫ ', '').trim();
                    }
                } else {
                    showStatus('❌ ' + result.message, 'error');
                    document.getElementById('active-' + lens).checked = !isActive;
                }
            } catch (e) {
                showStatus('❌ 操作失败: ' + e.message, 'error');
                document.getElementById('active-' + lens).checked = !isActive;
            }
        }
        
        async function deleteLens(lens) {
            if (!confirm('确定要删除棱镜 "' + lens + '" 吗？此操作不可撤销！')) return;
            
            try {
                const response = await fetch('/delete_lens/' + lens, { method: 'POST' });
                const result = await response.json();
                if (result.success) {
                    showStatus('✅ ' + result.message + '，页面将刷新...', 'success');
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showStatus('❌ ' + result.message, 'error');
                }
            } catch (e) {
                showStatus('❌ 删除失败: ' + e.message, 'error');
            }
        }
        
        // ========== 新建棱镜功能 ==========
        function showNewLensModal() {
            document.getElementById('newLensModal').style.display = 'flex';
        }
        
        function hideNewLensModal() {
            document.getElementById('newLensModal').style.display = 'none';
        }
        
        async function createNewLens() {
            const lensId = document.getElementById('newLensId').value.trim().toLowerCase();
            const lensName = document.getElementById('newLensName').value.trim();
            const lensDesc = document.getElementById('newLensDesc').value.trim();
            const xNegLabel = document.getElementById('newLensXNegLabel').value.trim();
            const xPosLabel = document.getElementById('newLensXPosLabel').value.trim();
            const yNegLabel = document.getElementById('newLensYNegLabel').value.trim();
            const yPosLabel = document.getElementById('newLensYPosLabel').value.trim();
            const xNeg = document.getElementById('newLensXNeg').value.trim();
            const xPos = document.getElementById('newLensXPos').value.trim();
            const yNeg = document.getElementById('newLensYNeg').value.trim();
            const yPos = document.getElementById('newLensYPos').value.trim();
            
            // 验证必填字段
            if (!lensId || !lensName) {
                showStatus('❌ 请填写棱镜 ID 和名称', 'error');
                return;
            }
            
            if (!/^[a-z][a-z0-9_]*$/.test(lensId)) {
                showStatus('❌ 棱镜 ID 只能包含小写字母、数字和下划线，且必须以字母开头', 'error');
                return;
            }
            
            showStatus('<span class="loading"></span>正在创建棱镜...', 'info');
            
            try {
                const response = await fetch('/create_lens', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: lensId,
                        name: lensName,
                        description: lensDesc || '自定义棱镜',
                        axes: {
                            x_label: { neg: xNegLabel || 'X-', pos: xPosLabel || 'X+' },
                            y_label: { neg: yNegLabel || 'Y-', pos: yPosLabel || 'Y+' }
                        },
                        axis_x_neg: xNeg || 'negative left',
                        axis_x_pos: xPos || 'positive right',
                        axis_y_neg: yNeg || 'negative bottom',
                        axis_y_pos: yPos || 'positive top'
                    })
                });
                
                const result = await response.json();
                if (result.success) {
                    showStatus('✅ ' + result.message + '，页面将刷新...', 'success');
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showStatus('❌ ' + result.message, 'error');
                }
            } catch (e) {
                showStatus('❌ 创建失败: ' + e.message, 'error');
            }
        }
        
        // 初始加载验证（动态获取所有棱镜）
        document.querySelectorAll('.tab[data-lens]').forEach(tab => {
            const lens = tab.dataset.lens;
            if (lens) validateLens(lens);
        });
    </script>
</body>
</html>
'''


def load_config():
    """加载配置"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            saved = json.load(f)
            # 合并默认配置和保存的配置
            config = DEFAULT_CONFIG.copy()
            for key, value in saved.items():
                if key in config:
                    # 更新默认棱镜
                    config[key].update(value)
                else:
                    # 添加自定义棱镜
                    config[key] = value
            return config
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """保存配置"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_lexicon(filepath):
    """加载词库（新三列格式：word_cn, word_en, semantic_hint）"""
    words = []
    if not filepath.exists():
        return words
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('word_'):
                continue
            parts = line.split(',')
            if len(parts) >= 2:
                word_cn = parts[0].strip()
                word_en = parts[1].strip()
                semantic_hint = parts[2].strip() if len(parts) >= 3 else ''
                words.append({
                    'cn': word_cn,
                    'en': word_en,
                    'hint': semantic_hint
                })
    return words


def rebuild_lens(lens_key, anchors, config):
    """重构单个棱镜的向量数据"""
    if not ML_AVAILABLE:
        return False, "ML 库未安装"
    
    # 加载模型
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    
    # 加载词库
    lexicon_file = BASE_DIR / config[lens_key]['lexicon_file']
    words = load_lexicon(lexicon_file)
    
    if not words:
        return False, f"词库为空: {lexicon_file}"
    
    # 编码锚点
    embeddings = {
        'x_neg': model.encode(anchors['axis_x_neg']),
        'x_pos': model.encode(anchors['axis_x_pos']),
        'y_neg': model.encode(anchors['axis_y_neg']),
        'y_pos': model.encode(anchors['axis_y_pos'])
    }
    
    # 定义锚点在 2D 空间的目标坐标 (0-100)
    # 遵循: X轴左右 (0, 100), Y轴下上 (0, 100)
    # 注意: App前端 0是上, 100是下? 不，通常 App 坐标系下 Y越大越往下。
    # 之前我们修复了前端，现在： Positive -> Top (Y=0或Y_small), Negative -> Bottom (Y=100或Y_large)
    # 再次确认 App.jsx:
    # Top Label (Positive) -> Y-
    # Bottom Label (Negative) -> Y+
    # 我们的目标是: 正向词(Positive) 在 Top, 负向词(Negative) 在 Bottom.
    # 所以: Y_Pos_Anchor -> (50, 0)   [屏幕上方]
    #      Y_Neg_Anchor -> (50, 100) [屏幕下方]
    #      X_Neg_Anchor -> (0, 50)   [屏幕左方]
    #      X_Pos_Anchor -> (100, 50) [屏幕右方]
    
    anchor_coords = {
        'x_neg': np.array([0, 50]),
        'x_pos': np.array([100, 50]),
        'y_neg': np.array([50, 100]), # Negative -> Bottom
        'y_pos': np.array([50, 0])    # Positive -> Top
    }
    
    points = []
    raw_x = []
    raw_y = []
    
    for word in words:
        # 编码词汇
        text_for_bert = word['en']
        if word.get('hint'):
            text_for_bert += ' ' + word['hint']
        
        word_emb = model.encode(text_for_bert)
        
        # 计算到四个极点的相似度 (Cos Sim: -1 ~ 1)
        sims = {}
        for key, anchor_emb in embeddings.items():
            sim = cosine_similarity(word_emb.reshape(1, -1), anchor_emb.reshape(1, -1))[0][0]
            # 映射到 [0, 1] 使得权重非负，且使用指数函数锐化差异 (Pulling Force)
            # exponent=3 让高相似度的锚点有更强的拉力
            sims[key] = np.power((sim + 1) / 2, 3) 

        # 重心坐标 (Weighted Barycentric Coordinates)
        # P = (Sum(w_i * P_i)) / Sum(w_i)
        total_weight = sum(sims.values())
        if total_weight == 0: total_weight = 1e-6
        
        w_x = 0
        w_y = 0
        for key, coord in anchor_coords.items():
            w_x += sims[key] * coord[0]
            w_y += sims[key] * coord[1]
            
        final_x = w_x / total_weight
        final_y = w_y / total_weight
        
        raw_x.append(final_x)
        raw_y.append(final_y)
        
        points.append({
            'word': word['en'],
            'zh': word['cn']
        })
    
    # 后处理：分位图归一化 (Quantile Normalization / Histogram Equalization)
    # 这一步强制把点的分布拉伸到均匀，解决“挤在中间”的问题
    from scipy.stats import rankdata
    
    raw_x = np.array(raw_x)
    raw_y = np.array(raw_y)
    
    # 将排名映射回 0-100 范围
    # rankdata 返回 1..N
    # (rank - 1) / (N - 1) * 100
    if len(raw_x) > 1:
        x_norm = (rankdata(raw_x) - 1) / (len(raw_x) - 1) * 100
        y_norm = (rankdata(raw_y) - 1) / (len(raw_y) - 1) * 100
    else:
        x_norm = raw_x
        y_norm = raw_y
        
    for i, point in enumerate(points):
        # 混合一下原始重心坐标和Rank坐标，保留一定的局部聚类特征，同时保证全局铺开
        # 混合比例: 0.3 原始 + 0.7 Rank (可调)
        # Rank 保证均匀，原始保证物理距离感
        mix_ratio = 0.7
        
        final_x = raw_x[i] * (1 - mix_ratio) + x_norm[i] * mix_ratio
        final_y = raw_y[i] * (1 - mix_ratio) + y_norm[i] * mix_ratio
        
        # 再次确保范围
        point['x'] = round(float(np.clip(final_x, 0, 100)), 1)
        point['y'] = round(float(np.clip(final_y, 0, 100)), 1)
    
    # 加载现有数据
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            output_data = json.load(f)
    else:
        output_data = {}
    
    # 更新棱镜数据
    output_data[lens_key] = {
        'name': config[lens_key]['name'],
        'description': config[lens_key]['description'],
        'axes': config[lens_key].get('axes', {}),
        'points': points
    }
    
    # 保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    # 更新配置
    config[lens_key].update(anchors)
    save_config(config)
    
    return True, f"成功重构 (Anchored MDS) {lens_key}，共 {len(points)} 个词汇"


def get_validation(lens_key):
    """获取验证数据"""
    if not OUTPUT_FILE.exists():
        return None
    
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if lens_key not in data:
        return None
    
    points = data[lens_key]['points']
    config = load_config()
    
    # 从 CSV 加载完整词库（包含语义提示）
    lexicon_file = BASE_DIR / config[lens_key]['lexicon_file']
    lexicon_words = load_lexicon(lexicon_file)
    
    # 创建英文到语义提示的映射
    hint_map = {w['en']: w.get('hint', '') for w in lexicon_words}
    
    # 分象限
    quadrants = {
        'tl': {'count': 0, 'samples': []},
        'tr': {'count': 0, 'samples': []},
        'bl': {'count': 0, 'samples': []},
        'br': {'count': 0, 'samples': []}
    }
    
    for p in points:
        x, y = p['x'], p['y']
        if x < 50 and y < 50:
            q = 'tl'
        elif x >= 50 and y < 50:
            q = 'tr'
        elif x < 50 and y >= 50:
            q = 'bl'
        else:
            q = 'br'
        
        quadrants[q]['count'] += 1
        if len(quadrants[q]['samples']) < 5:
            # 返回完整信息：中文、英文、语义提示
            sample = {
                'cn': p['zh'],
                'en': p['word'],
                'hint': hint_map.get(p['word'], '')
            }
            quadrants[q]['samples'].append(sample)
    
    # 获取标签
    axes = config[lens_key]['axes']
    labels = {
        'tl': f"({axes['x_label']['neg'].split('/')[0]} + {axes['y_label']['neg'].split('/')[0]})",
        'tr': f"({axes['x_label']['pos'].split('/')[0]} + {axes['y_label']['neg'].split('/')[0]})",
        'bl': f"({axes['x_label']['neg'].split('/')[0]} + {axes['y_label']['pos'].split('/')[0]})",
        'br': f"({axes['x_label']['pos'].split('/')[0]} + {axes['y_label']['pos'].split('/')[0]})"
    }
    
    return {
        'quadrants': quadrants,
        'labels': labels,
        'total': len(points)
    }


@app.route('/')
def index():
    config = load_config()
    return render_template_string(HTML_TEMPLATE, config=config, ml_available=ML_AVAILABLE)


@app.route('/rebuild', methods=['POST'])
def rebuild():
    if not ML_AVAILABLE:
        return jsonify({'success': False, 'message': 'ML 库未安装'})
    
    data = request.json
    lens = data.get('lens')
    anchors = data.get('anchors')
    
    config = load_config()
    success, message = rebuild_lens(lens, anchors, config)
    
    return jsonify({'success': success, 'message': message})


@app.route('/rebuild_all', methods=['POST'])
def rebuild_all():
    if not ML_AVAILABLE:
        return jsonify({'success': False, 'message': 'ML 库未安装'})
    
    all_anchors = request.json
    config = load_config()
    
    results = []
    for lens, anchors in all_anchors.items():
        success, message = rebuild_lens(lens, anchors, config)
        results.append(f"{lens}: {message}")
    
    return jsonify({
        'success': True,
        'message': ' | '.join(results)
    })


@app.route('/validate/<lens>')
def validate(lens):
    result = get_validation(lens)
    if result:
        return jsonify({'success': True, **result})
    return jsonify({'success': False, 'message': '无数据'})


@app.route('/reset/<lens>', methods=['POST'])
def reset(lens):
    config = load_config()
    if lens in DEFAULT_CONFIG:
        config[lens] = DEFAULT_CONFIG[lens].copy()
        save_config(config)
        return jsonify({'success': True})
    return jsonify({'success': False})


@app.route('/create_lens', methods=['POST'])
def create_lens():
    """创建新棱镜"""
    data = request.json
    lens_id = data.get('id', '').strip().lower()
    
    # 验证 ID
    if not lens_id:
        return jsonify({'success': False, 'message': '棱镜 ID 不能为空'})
    
    import re
    if not re.match(r'^[a-z][a-z0-9_]*$', lens_id):
        return jsonify({'success': False, 'message': '棱镜 ID 格式不正确'})
    
    # 检查是否已存在
    config = load_config()
    if lens_id in config:
        return jsonify({'success': False, 'message': f'棱镜 {lens_id} 已存在'})
    
    # 创建新棱镜配置
    new_lens = {
        'name': data.get('name', f'{lens_id.capitalize()} Lens'),
        'description': data.get('description', '自定义棱镜'),
        'lexicon_file': f'lexicon_{lens_id}.csv',
        'axes': data.get('axes', {
            'x_label': {'neg': 'X-', 'pos': 'X+'},
            'y_label': {'neg': 'Y-', 'pos': 'Y+'}
        }),
        'axis_x_neg': data.get('axis_x_neg', 'negative left'),
        'axis_x_pos': data.get('axis_x_pos', 'positive right'),
        'axis_y_neg': data.get('axis_y_neg', 'negative bottom'),
        'axis_y_pos': data.get('axis_y_pos', 'positive top')
    }
    
    # 创建空的词库文件
    lexicon_file = BASE_DIR / new_lens['lexicon_file']
    if not lexicon_file.exists():
        with open(lexicon_file, 'w', encoding='utf-8') as f:
            f.write('word_cn,word_en,semantic_hint\n')
            f.write(f'# ========== {new_lens["name"]} 词库 ==========\n')
            f.write(f'# X轴: {new_lens["axes"]["x_label"]["neg"]} <-> {new_lens["axes"]["x_label"]["pos"]}\n')
            f.write(f'# Y轴: {new_lens["axes"]["y_label"]["neg"]} <-> {new_lens["axes"]["y_label"]["pos"]}\n')
            f.write('\n')
            f.write('# 在此添加词汇，格式: 中文,英文,语义提示\n')
            f.write('# 例如: 示例词,Example,hint words\n')
    
    # 保存配置
    config[lens_id] = new_lens
    save_config(config)
    
    return jsonify({
        'success': True, 
        'message': f'棱镜 {lens_id} 创建成功！词库文件: {new_lens["lexicon_file"]}'
    })


@app.route('/toggle_active/<lens>', methods=['POST'])
def toggle_active(lens):
    """切换棱镜激活状态"""
    config = load_config()
    
    if lens not in config:
        return jsonify({'success': False, 'message': f'棱镜 {lens} 不存在'})
    
    data = request.json
    is_active = data.get('active', True)
    
    config[lens]['active'] = is_active
    save_config(config)
    
    status = '已激活' if is_active else '已禁用'
    return jsonify({'success': True, 'message': f'棱镜 {lens} {status}'})


@app.route('/delete_lens/<lens>', methods=['POST'])
def delete_lens(lens):
    """删除棱镜"""
    config = load_config()
    
    # 不允许删除默认棱镜
    if lens in DEFAULT_CONFIG:
        return jsonify({'success': False, 'message': '不能删除默认棱镜'})
    
    if lens not in config:
        return jsonify({'success': False, 'message': f'棱镜 {lens} 不存在'})
    
    # 删除配置
    del config[lens]
    save_config(config)
    
    return jsonify({'success': True, 'message': f'棱镜 {lens} 已删除'})


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("🎛️  锚点编辑器 - Anchor Editor")
    print("=" * 50)
    print(f"\n📂 配置文件: {CONFIG_FILE}")
    print(f"📂 输出文件: {OUTPUT_FILE}")
    print(f"\n🌐 请访问: http://localhost:5001")
    print("\n按 Ctrl+C 停止服务器\n")
    
    app.run(host='0.0.0.0', port=5001, debug=False)

