#!/usr/bin/env python3
"""
锚点编辑器 v2.0 - Anchor Map Editor
===================================
Project Synesth 核心工具升级版
功能：
1. 可视化力场编辑：拖拽锚点(Pin)来定义语义空间的物理坐标
2. 多点基函数插值 (RBF/IDW)：基于多个自定义锚点生成高精度语义映射
3. 兼容性：首次运行时自动将旧版"四极配置"转换为"空间锚点"

启动方式：
    python anchor_editor_v2.py
访问: http://localhost:5001
"""

import json
import os
import random
import math
import re
import time
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, Response
import numpy as np

# 尝试导入 ML 库
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    from scipy.interpolate import Rbf
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("警告: 缺少依赖 (sentence-transformers, scipy)，核心算法将不可用")

app = Flask(__name__)

# 路径配置
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "anchor_config_v2.json"
OLD_CONFIG_FILE = BASE_DIR / "anchor_config.json"
OUTPUT_FILE = BASE_DIR.parent / "webapp" / "public" / "data" / "sonic_vectors.json"

# 系统保留的棱镜 ID (不可用于新建棱镜)
# 注意：不再限制特定ID，用户可以创建任何新的棱镜
RESERVED_IDS = {'test'}  # 仅保留测试ID作为保留

# v2 默认配置结构 (如果没有 v1 迁移的话)
DEFAULT_CONFIG_V2 = {
    "texture": {
        "name": "Texture / Timbre (质感)",
        "description": "声音的质感和情绪色彩",
        "lexicon_file": "lexicon_texture.csv",
        "axes": {
            "x_label": {"neg": "Dark / 黑暗恐惧", "pos": "Light / 光明治愈"},
            "y_label": {"neg": "Serious / 写实严肃", "pos": "Playful / 趣味活跃"} # Fixed order
        },
        "anchors": [] # List of {word: "", x: 0, y: 0}
    },
    "source": {
        "name": "Source & Physics (源场)",
        "description": "声音的物理特征与来源属性",
        "lexicon_file": "lexicon_source.csv",
        "axes": {
            "x_label": {"neg": "Static / 静态铺底", "pos": "Transient / 瞬态冲击"},
            "y_label": {"neg": "Organic / 有机自然", "pos": "Sci-Fi / 科幻合成"} # Fixed order
        },
        "anchors": []
    },
    "materiality": {
        "name": "Materiality / Room (材质)",
        "description": "声音的空间材质与距离特征",
        "lexicon_file": "lexicon_materiality.csv",
        "axes": {
            "x_label": {"neg": "Close / 贴耳干涩", "pos": "Distant / 遥远湿润"},
            "y_label": {"neg": "Warm / 暖软吸音", "pos": "Cold / 冷硬反射"} # Fixed order
        },
        "anchors": []
    }
}

# ==========================================
# 核心算法：多点加权插值 (Weighted Interpolation)
# ==========================================

def rebuild_lens_v2_gen(lens_key, config, override_categories=None, model_name="paraphrase-multilingual-MiniLM-L12-v2"):
    if not ML_AVAILABLE:
        yield "data: " + json.dumps({"error": "ML 库未安装"}) + "\n\n"
        return
    
    lens_data = config[lens_key]
    anchors = lens_data.get('anchors', [])
    if not anchors:
        yield "data: " + json.dumps({"error": "该棱镜没有定义任何锚点"}) + "\n\n"
        return

    yield "data: " + json.dumps({"progress": 10, "status": f"正在加载语义模型 ({model_name})..."}) + "\n\n"
    try:
        model = SentenceTransformer(model_name)
    except Exception as e:
        yield "data: " + json.dumps({"error": f"加载模型失败: {e}"}) + "\n\n"
        return
    
    yield "data: " + json.dumps({"progress": 30, "status": f"正在编码 {len(anchors)} 个锚点..."}) + "\n\n"
    anchor_embs = []
    anchor_coords = []
    valid_anchors = []
    for a in anchors:
        w = a['word'].strip()
        if not w: continue
        valid_anchors.append(a)
        anchor_embs.append(model.encode(w))
        anchor_coords.append([a['x'], a['y']])
    
    anchor_embs = np.array(anchor_embs)
    anchor_coords = np.array(anchor_coords)
    
    # 3. 加载并过滤词库
    lexicon_file = BASE_DIR / lens_data['lexicon_file']
    all_words = load_lexicon(lexicon_file)

    # 检查词库是否有 category 字段
    has_category = any(w.get('category') for w in all_words)

    # 类别过滤：优先使用前端传来的覆盖参数，其次使用配置中的默认设置
    filter_cats = override_categories if override_categories else lens_data.get('filter_categories')

    if filter_cats and has_category:
        # 只有当词库有 category 字段时才进行过滤
        words = [w for w in all_words if w.get('category') in filter_cats]
        status_msg = f"加载词库 ({len(words)}/{len(all_words)} 词经过类目过滤)..."
    elif filter_cats and not has_category:
        # 词库没有 category 字段，忽略过滤
        words = all_words
        status_msg = f"加载词库 ({len(all_words)} 词，无类别标记，已忽略过滤)..."
    else:
        words = all_words
        status_msg = f"开始计算 {len(words)} 个词汇的归属..."

    if not words:
        yield "data: " + json.dumps({"error": "没有找到符合类目要求的词"}) + "\n\n"
        return
    
    yield "data: " + json.dumps({"progress": 40, "status": status_msg}) + "\n\n"
    
    raw_points = []
    xs, ys = [], []
    total = len(words)
    
    for i, word_obj in enumerate(words):
        text = word_obj['en']
        if word_obj.get('hint'):
            text += ' ' + word_obj['hint']
            
        word_emb = model.encode(text)
        sims = cosine_similarity(word_emb.reshape(1, -1), anchor_embs)[0]
        weights = np.power((sims + 1) / 2, 8) 
        
        total_weight = np.sum(weights)
        if total_weight < 1e-9:
            final_x, final_y = 50.0, 50.0
        else:
            weighted_coords = np.dot(weights, anchor_coords) 
            final_x = weighted_coords[0] / total_weight
            final_y = weighted_coords[1] / total_weight
            
        raw_points.append({'word_obj': word_obj, 'x': final_x, 'y': final_y})
        xs.append(final_x)
        ys.append(final_y)
        
        if i % 10 == 0 or i == total - 1:
            prog = 40 + int((i / total) * 50)
            yield "data: " + json.dumps({"progress": prog, "status": f"已处理 {i+1}/{total}..."}) + "\n\n"

    yield "data: " + json.dumps({"progress": 95, "status": "正在进行空间均匀化变换..."}) + "\n\n"
    
    xs, ys = np.array(xs), np.array(ys)
    xs, ys = np.array(xs), np.array(ys)
    def smooth_stretch(vals, target_min=5, target_max=95):
        if len(vals) < 2: return np.full_like(vals, 50.0)
        # 使用 scipy.stats.rankdata 处理并列排名 (ties)
        from scipy.stats import rankdata
        ranks = rankdata(vals, method='average')
        # 归一化到 [0, 1]
        norm = (ranks - np.min(ranks)) / (np.max(ranks) - np.min(ranks) + 1e-9)
        return norm * (target_max - target_min) + target_min

    stretched_xs = smooth_stretch(xs)
    stretched_ys = smooth_stretch(ys)
    
    points = []
    for i, p in enumerate(raw_points):
        points.append({
            'id': f"{lens_key}_{i}", # 增加唯一 ID
            'word': p['word_obj']['en'],
            'zh': p['word_obj']['cn'],
            'x': round(float(np.clip(stretched_xs[i], 0, 100)), 1),
            'y': round(float(np.clip(stretched_ys[i], 0, 100)), 1)
        })

    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            output_data = json.load(f)
    else:
        output_data = {}
        
    output_data[lens_key] = {
        'name': lens_data['name'],
        'description': lens_data['description'],
        'axes': lens_data['axes'],
        'points': points
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
        
    # --- Phase C4: 将预计算的力场同步到数据库，以便推送到云端 ---
    try:
        db_path = BASE_DIR / "database" / "capsules.db"
        if db_path.exists():
            import sqlite3
            conn = sqlite3.connect(db_path)
            # 更新 prisms 表中的 field_data 字段
            conn.execute("""
                UPDATE prisms 
                SET field_data = ?, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (json.dumps(points, ensure_ascii=False), lens_key))
            conn.commit()
            conn.close()
            print(f"✅ 已将 {len(points)} 个词汇的坐标同步到数据库棱镜表 '{lens_key}'")
    except Exception as e:
        print(f"⚠️  同步力场到数据库失败: {e}")
        
    yield "data: " + json.dumps({"progress": 100, "message": f"重构完成，由 {len(valid_anchors)} 个锚点定义力场"}) + "\n\n"

# ==========================================
# 辅助函数
# ==========================================

def load_lexicon(filepath):
    words = []
    if not filepath.exists(): return words
    with open(filepath, 'r', encoding='utf-8') as f:
        # 尝试读取第一行判断列名
        header = f.readline().strip().split(',')
        has_category = 'category' in [h.strip() for h in header]
        
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            parts = line.split(',')
            if len(parts) >= 2:
                word_obj = {
                    'cn': parts[0].strip(),
                    'en': parts[1].strip(),
                    'hint': parts[2].strip() if len(parts) >= 3 else ''
                }
                if has_category and len(parts) >= 4:
                    word_obj['category'] = parts[3].strip()
                words.append(word_obj)
    return words

def load_config_v2():
    # 优先加载 v2 配置
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    # 如果没有 v2，尝试从 v1 迁移
    if OLD_CONFIG_FILE.exists():
        print("Migrating v1 config to v2...")
        with open(OLD_CONFIG_FILE, 'r', encoding='utf-8') as f:
            old_conf = json.load(f)
            
        new_conf = {}
        for key, val in old_conf.items():
            new_lens = {
                "name": val['name'],
                "description": val.get('description', ''),
                "lexicon_file": val.get('lexicon_file', f'lexicon_{key}.csv'),
                "axes": val.get('axes', {
                    "x_label": {"neg": "Left", "pos": "Right"},
                    "y_label": {"neg": "Bottom", "pos": "Top"}
                }),
                "anchors": []
            }
            
            # 将旧的字符串锚点转换为空间锚点
            # 策略：随机撒在对应区域，避免重叠
            
            def parse_words(text):
                return [w.strip() for w in text.split(' ') if w.strip()]
            
            # X Neg (Left): x ~ 5-15, y ~ 20-80
            for w in parse_words(val.get('axis_x_neg', '')):
                new_lens['anchors'].append({"word": w, "x": random.uniform(2, 10), "y": random.uniform(20, 80)})
                
            # X Pos (Right): x ~ 85-95, y ~ 20-80
            for w in parse_words(val.get('axis_x_pos', '')):
                new_lens['anchors'].append({"word": w, "x": random.uniform(90, 98), "y": random.uniform(20, 80)})
                
            # Y Neg (Bottom in v2 UI -> Y=100? No, checking App.jsx fix)
            # 刚才我们修复了 App.jsx: Top is Positive, Bottom is Negative.
            # 可是通常 CSS top:0 是最上面。
            # 无论如何，我们定义：
            # Y=0 (Top) -> Positive Anchor Region
            # Y=100 (Bottom) -> Negative Anchor Region
            
            # Y Neg (Original label) -> usually means Bottom in semantic?
            # 让我们遵循 v1 逻辑：axis_y_neg 是一组词，axis_y_pos 是另一组
            # 在 Texture 里: neg=Serious, pos=Playful
            # 在新 App.jsx: Top=Playful, Bottom=Serious
            # 所以:
            # axis_y_pos (Playful) -> Top (Y=0~10)
            # axis_y_neg (Serious) -> Bottom (Y=90~100)
            
            for w in parse_words(val.get('axis_y_pos', '')): # Positive -> Top
                new_lens['anchors'].append({"word": w, "x": random.uniform(20, 80), "y": random.uniform(2, 10)})
                
            for w in parse_words(val.get('axis_y_neg', '')): # Negative -> Bottom
                new_lens['anchors'].append({"word": w, "x": random.uniform(20, 80), "y": random.uniform(90, 98)})
            
            new_conf[key] = new_lens
            
        save_config_v2(new_conf)
        return new_conf
        
    return DEFAULT_CONFIG_V2.copy()

def save_config_v2(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def create_lens_config(data: dict) -> dict:
    """
    创建新棱镜的默认配置

    Args:
        data: 包含 id, name, description, axes 等字段的字典

    Returns:
        完整的棱镜配置字典
    """
    lens_id = data.get('id', 'new_lens')
    name = data.get('name', '')
    description = data.get('description', '')

    # 如果 name 只包含英文或中文，自动生成中英文对照格式
    # 格式: "English / (中文)"
    if ' / ' not in name:
        # 假设 name 是纯英文或纯中文，生成默认格式
        # 如果是英文，格式为 "Name / (ID)"
        # 如果是中文，格式为 "ID / (中文名称)"
        name_formatted = f"{lens_id.capitalize()} / ({name})"
    else:
        name_formatted = name

    # 格式化轴标签为 "English / (中文)" 格式
    axes = data.get('axes', {
        'x_label': {'neg': 'Left / (负向)', 'pos': 'Right / (正向)'},
        'y_label': {'neg': 'Bottom / (负向)', 'pos': 'Top / (正向)'}
    })

    # 确保每个轴标签都是 "English / (中文)" 格式
    for axis in ['x_label', 'y_label']:
        if axis in axes:
            for direction in ['neg', 'pos']:
                if direction in axes[axis]:
                    current = axes[axis][direction]
                    # 如果不包含 " / "，说明用户只输入了英文或中文
                    # 这种情况下保持原样，让用户自己输入完整的格式
                    if ' / ' not in current:
                        # 不自动添加，保持用户输入
                        axes[axis][direction] = current

    return {
        'name': name_formatted,
        'description': description,
        'lexicon_file': data.get('lexicon_file', f'lexicon_{lens_id}.csv'),
        'axes': axes,
        'anchors': []  # 初始无锚点，用户手动添加或导入
    }

# ==========================================
# Flask Routes
# ==========================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# 预置翻译字典 (作为 AI 助手，我会持续补充这个字典)
TRANS_DICT = {
    "恶魔": "demon", "魔鬼": "devil", "地狱": "hell", "圣光": "holy light", "天堂": "heaven",
    "撞击": "impact", "打击": "hit", "爆炸": "explosion", "舒缓": "soothing", "放松": "relaxing",
    "柔和": "soft", "清脆": "crisp", "沉重": "heavy", "轻盈": "lightweight", "科幻": "sci-fi",
    "机械": "mechanical", "自然": "natural", "有机": "organic", "金属": "metallic", "木质": "woody",
    "水": "water", "火": "fire", "风": "wind", "雷": "thunder", "电": "electric", "魔法": "magic",
    "黑暗": "dark", "明亮": "bright", "寒冷": "cold", "温暖": "warm", "粗糙": "rough", "平滑": "smooth"
}

def auto_translate(word):
    """检测中文并尝试翻译"""
    if any('\u4e00' <= char <= '\u9fff' for char in word):
        # 如果在字典里，返回翻译
        if word in TRANS_DICT:
            return TRANS_DICT[word], word
        return word, word # 没找到翻译则暂时保持原样
    return word, None

@app.route('/api/config', methods=['GET'])
def get_config():
    conf = load_config_v2()
    # Enrich anchors with Chinese translations from lexicons
    for lens_key, lens_data in conf.items():
        lex_file = BASE_DIR / lens_data.get('lexicon_file', '')
        if lex_file.exists():
            words = load_lexicon(lex_file)
            # Build map: lowercase en -> cn (exact match)
            trans_map = {}
            for w in words:
                trans_map[w['en'].lower()] = w['cn']
            
            # Build partial match map (for compound words)
            partial_map = {}
            for w in words:
                en_lower = w['en'].lower()
                # Split compound words and index each part
                parts = en_lower.replace(',', ' ').replace('-', ' ').split()
                for part in parts:
                    if len(part) > 2:  # Ignore very short words
                        if part not in partial_map:
                            partial_map[part] = []
                        partial_map[part].append(w['cn'])
            
            for anchor in lens_data.get('anchors', []):
                w_lower = anchor['word'].lower()
                # Try exact match first
                if w_lower in trans_map:
                    anchor['zh'] = trans_map[w_lower]
                # Try partial match (if anchor word appears in compound)
                elif w_lower in partial_map:
                    # Use the first match
                    anchor['zh'] = partial_map[w_lower][0]
    return jsonify(conf)

@app.route('/api/config', methods=['POST'])
def update_config():
    new_conf = request.json
    
    # 自动翻译锚点词
    for lens_key, lens_data in new_conf.items():
        for anchor in lens_data.get('anchors', []):
            word = anchor.get('word', '')
            en_word, zh_label = auto_translate(word)
            if zh_label:
                anchor['word'] = en_word
                anchor['zh'] = zh_label
    
    save_config_v2(new_conf)
    return jsonify({"success": True})

@app.route('/api/rebuild/<lens>', methods=['POST'])
def rebuild(lens):
    # 此接口保留作为同步备份，或改为调用 Generator 的最后结果
    config = load_config_v2()
    # 为了进度条，我们通常建议使用下面的 stream 接口
    # 如果用户直接调用这个，我们返回简短成功
    return jsonify({"success": True})

@app.route('/api/rebuild_stream/<lens>')
def rebuild_stream(lens):
    config = load_config_v2()
    # 从查询参数中获取选中的分类
    categories_str = request.args.get('categories', '')
    categories = categories_str.split(',') if categories_str else None
    
    # 获取选中的模型
    model_name = request.args.get('model', 'paraphrase-multilingual-MiniLM-L12-v2')

    return Response(rebuild_lens_v2_gen(lens, config, categories, model_name), mimetype='text/event-stream')

@app.route('/api/sync/cloud', methods=['POST'])
def sync_to_cloud():
    """同步棱镜配置和坐标到云端 (Supabase)"""
    try:
        from sync_service import SyncService
        from prism_version_manager import PrismVersionManager
        
        db_path = str(BASE_DIR / "database" / "capsules.db")
        sync_svc = SyncService(db_path)
        pm = PrismVersionManager(db_path)
        
        # 1. 获取当前活跃用户
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        user = conn.execute("SELECT supabase_user_id FROM users WHERE is_active = 1").fetchone()
        conn.close()
        
        if not user or not user['supabase_user_id']:
            return jsonify({"success": False, "error": "请先在胶囊客户端登录 Supabase 账号"})
            
        user_id = user['supabase_user_id']
        
        # 2. 将本地 JSON 配置同步到本地数据库（作为同步源）
        # 增加逻辑：从外部 sonic_vectors.json 获取预计算坐标，合并回配置中
        config = load_config_v2()
        vector_path = BASE_DIR.parent / "webapp" / "public" / "data" / "sonic_vectors.json"
        
        if vector_path.exists():
            try:
                with open(vector_path, 'r', encoding='utf-8') as f:
                    vector_data = json.load(f)
                    for lid, linfo in vector_data.items():
                        if lid in config:
                            config[lid]['field_data'] = linfo.get('points', [])
                print(f"✅ 从 sonic_vectors.json 合并了 {len(vector_data)} 个力场数据")
            except Exception as e:
                print(f"⚠️ 合并力场数据失败: {e}")

        for lens_id, lens_data in config.items():
            pm.create_or_update_prism(lens_id, lens_data, user_id="editor_sync")
            
        # 3. 执行同步
        print(f"🚀 开始为用户 {user_id} 同步数据到云端...")
        
        # 同步棱镜
        prism_result = sync_svc.sync_prisms(user_id)
        
        # 同步坐标 (元数据)
        capsule_result = sync_svc.sync_metadata_lightweight(user_id)
        
        return jsonify({
            "success": True,
            "prisms": prism_result,
            "capsules": capsule_result,
            "message": "同步完成"
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})

# ==========================================
# 棱镜 CRUD API (v3.0 新增)
# ==========================================

@app.route('/api/lenses', methods=['POST'])
def create_lens():
    """
    创建新棱镜

    Request Body:
    {
        "id": "my_lens",
        "name": "My Lens",
        "description": "描述",
        "axes": {
            "x_label": {"neg": "左", "pos": "右"},
            "y_label": {"neg": "下", "pos": "上"}
        }
    }
    """
    try:
        data = request.json
        lens_id = data.get('id', '').strip().lower()

        # 验证 ID 格式：只能包含小写字母、数字、下划线，且以字母开头
        if not re.match(r'^[a-z][a-z0-9_]*$', lens_id):
            return jsonify({
                "success": False,
                "error": "ID 格式无效。必须以小写字母开头，只能包含小写字母、数字和下划线"
            }), 400

        # 检查是否为系统保留 ID
        if lens_id in RESERVED_IDS:
            return jsonify({
                "success": False,
                "error": f"'{lens_id}' 是系统保留 ID，不可使用",
                "suggestion": f"{lens_id}_custom",
                "reserved_ids": list(RESERVED_IDS)
            }), 409

        # 加载当前配置
        config = load_config_v2()

        # 检查 ID 是否已存在
        if lens_id in config:
            timestamp = int(time.time())
            return jsonify({
                "success": False,
                "error": f"棱镜 '{lens_id}' 已存在",
                "options": [
                    f"{lens_id}_copy",
                    f"{lens_id}_{timestamp}",
                    f"{lens_id}_v2"
                ]
            }), 409

        # 创建新棱镜配置
        config[lens_id] = create_lens_config(data)

        # 自动创建对应的 CSV 词库文件（如果不存在）
        lexicon_file = config[lens_id]['lexicon_file']
        lexicon_path = BASE_DIR / lexicon_file

        csv_created = False
        if not lexicon_path.exists():
            try:
                # 创建带有基本表头的 CSV 文件
                with open(lexicon_path, 'w', encoding='utf-8') as f:
                    f.write('word_cn,word_en,semantic_hint\n')
                csv_created = True
                print(f"Created lexicon file: {lexicon_file}")
            except Exception as e:
                print(f"Warning: Failed to create lexicon file: {e}")

        save_config_v2(config)

        # 保存历史快照
        try:
            from lens_history import save_lens_snapshot
            save_lens_snapshot(lens_id, config[lens_id],
                             action="create",
                             description="创建新棱镜")
        except Exception as e:
            print(f"Warning: Failed to save history snapshot: {e}")

        # 构建返回消息
        message = f"成功创建棱镜 '{lens_id}'"
        if csv_created:
            message += f"，已创建词库文件: {lexicon_file}"

        return jsonify({
            "success": True,
            "lens_id": lens_id,
            "message": message,
            "lexicon_file": lexicon_file,
            "csv_created": csv_created
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"创建失败: {str(e)}"
        }), 500


@app.route('/api/lenses/<lens_id>', methods=['DELETE'])
def delete_lens(lens_id):
    """
    删除棱镜

    注意：
    - 胶囊的标签数据不会被删除（孤儿标签机制）
    - 对应的 CSV 词库文件会被重命名（加上 _deleted_ 前缀）
    """
    try:
        config = load_config_v2()

        if lens_id not in config:
            return jsonify({
                "success": False,
                "error": f"棱镜 '{lens_id}' 不存在"
            }), 404

        # 保存删除前的快照
        try:
            from lens_history import save_lens_snapshot
            save_lens_snapshot(lens_id, config[lens_id],
                             action="delete",
                             description="删除棱镜前")
        except Exception as e:
            print(f"Warning: Failed to save history snapshot: {e}")

        # 重命名对应的 CSV 词库文件
        lexicon_file = config[lens_id].get('lexicon_file', '')
        renamed_file = None
        if lexicon_file:
            lexicon_path = BASE_DIR / lexicon_file
            if lexicon_path.exists():
                try:
                    # 生成新文件名：deleted_原始名_时间戳.csv
                    timestamp = time.strftime('%Y%m%d_%H%M%S')
                    new_filename = f"deleted_{lexicon_path.stem}_{timestamp}.csv"
                    new_path = BASE_DIR / new_filename

                    # 重命名文件
                    lexicon_path.rename(new_path)
                    renamed_file = new_filename
                    print(f"Renamed lexicon: {lexicon_file} -> {new_filename}")
                except Exception as e:
                    print(f"Warning: Failed to rename lexicon file: {e}")

        # 删除棱镜
        del config[lens_id]
        save_config_v2(config)

        message = f"成功删除棱镜 '{lens_id}'"
        if renamed_file:
            message += f"，词库文件已重命名为: {renamed_file}"

        return jsonify({
            "success": True,
            "message": message,
            "note": "胶囊标签数据已保留（孤儿标签）",
            "renamed_lexicon": renamed_file
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"删除失败: {str(e)}"
        }), 500


@app.route('/api/lenses/<lens_id>', methods=['PUT'])
def update_lens(lens_id):
    """
    更新棱镜配置

    Request Body:
    {
        "name": "Updated Name",
        "description": "新描述",
        "axes": {...}
    }
    """
    try:
        config = load_config_v2()

        if lens_id not in config:
            return jsonify({
                "success": False,
                "error": f"棱镜 '{lens_id}' 不存在"
            }), 404

        # 保存更新前的快照
        try:
            from lens_history import save_lens_snapshot
            save_lens_snapshot(lens_id, config[lens_id],
                             action="before_update",
                             description="更新前的状态")
        except Exception as e:
            print(f"Warning: Failed to save history snapshot: {e}")

        # 更新配置
        data = request.json
        if 'name' in data:
            config[lens_id]['name'] = data['name']
        if 'description' in data:
            config[lens_id]['description'] = data['description']
        if 'axes' in data:
            config[lens_id]['axes'] = data['axes']
        if 'lexicon_file' in data:
            config[lens_id]['lexicon_file'] = data['lexicon_file']

        save_config_v2(config)

        return jsonify({
            "success": True,
            "message": f"成功更新棱镜 '{lens_id}'"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"更新失败: {str(e)}"
        }), 500


@app.route('/api/lenses/<lens_id>/toggle-active', methods=['POST'])
def toggle_lens_active(lens_id):
    """
    切换棱镜的激活/禁用状态
    
    Request Body:
    {
        "active": true/false
    }
    
    Response:
    {
        "success": true,
        "lens_id": "mechanics",
        "active": false,
        "message": "棱镜 'mechanics' 已禁用"
    }
    """
    try:
        config = load_config_v2()
        
        if lens_id not in config:
            return jsonify({
                "success": False,
                "error": f"棱镜 '{lens_id}' 不存在"
            }), 404
        
        data = request.json or {}
        # 如果没有提供 active，则切换当前状态
        current_active = config[lens_id].get('active', True)
        new_active = data.get('active', not current_active)
        
        config[lens_id]['active'] = new_active
        save_config_v2(config)
        
        status = '已激活' if new_active else '已禁用'
        
        return jsonify({
            "success": True,
            "lens_id": lens_id,
            "active": new_active,
            "message": f"棱镜 '{lens_id}' {status}"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"切换状态失败: {str(e)}"
        }), 500


@app.route('/api/lenses/<lens_id>/generate-anchors', methods=['POST'])
def generate_suggested_anchors(lens_id):
    """
    智能生成建议锚点

    Request Body:
    {
        "count_per_quadrant": 5,  // 每个象限生成多少个锚点，默认5
        "pos_filter": ["noun", "verb", "adjective"],  // 可选：词性过滤
        "axes": {  // 可选：临时轴配置（用于创建棱镜前的预览）
            "x_label": {"neg": "...", "pos": "..."},
            "y_label": {"neg": "...", "pos": "..."}
        }
    }

    返回:
    {
        "success": true,
        "anchors": [...],
        "message": "成功生成 20 个建议锚点",
        "pos_filter": ["adjective"]  // 实际使用的词性过滤
    }
    """
    try:
        # 获取参数
        data = request.json or {}
        count_per_quadrant = data.get('count_per_quadrant', 5)
        pos_filter = data.get('pos_filter', None)  # 获取词性过滤参数

        # 确定使用哪个轴配置
        axes = data.get('axes')  # 优先使用请求中的临时轴配置
        if not axes:
            # 否则从现有棱镜配置中读取
            config = load_config_v2()
            if lens_id not in config:
                return jsonify({
                    "success": False,
                    "error": f"棱镜 '{lens_id}' 不存在，且未提供临时轴配置"
                }), 404
            axes = config[lens_id].get('axes', {})

        # 导入生成器
        try:
            from anchor_generator import get_generator
            generator = get_generator()

            if not generator.model:
                return jsonify({
                    "success": False,
                    "error": "语义模型未加载，无法生成锚点"
                }), 500

            # 生成锚点（传入词性过滤参数）
            suggested_anchors = generator.generate_all_anchors(
                axes,
                count_per_quadrant,
                pos_filter=pos_filter
            )

            # 构建响应消息
            message = f"成功生成 {len(suggested_anchors)} 个建议锚点"
            if pos_filter:
                # 英文词性名称映射
                pos_names = {
                    'noun': '名词',
                    'verb': '动词',
                    'adjective': '形容词',
                    'adverb': '副词'
                }
                pos_text = '、'.join([pos_names.get(p, p) for p in pos_filter])
                message += f"（{pos_text}）"

            return jsonify({
                "success": True,
                "anchors": suggested_anchors,
                "message": message,
                "pos_filter": pos_filter,
                "unique_words": len(set(a['word'] for a in suggested_anchors))
            })

        except ImportError as e:
            return jsonify({
                "success": False,
                "error": f"无法导入锚点生成器: {str(e)}"
            }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"生成失败: {str(e)}"
        }), 500


# ==========================================
# 锚点导入/导出 API
# ==========================================

@app.route('/api/lenses/<lens_id>/anchors/export', methods=['GET'])
def export_anchors(lens_id):
    """
    导出锚点为 CSV 文件

    CSV 格式: word,x,y,zh
    """
    try:
        config = load_config_v2()

        if lens_id not in config:
            return jsonify({
                "success": False,
                "error": f"棱镜 '{lens_id}' 不存在"
            }), 404

        anchors = config[lens_id].get('anchors', [])

        # 生成 CSV 内容
        csv_lines = ["word,x,y,zh"]
        for anchor in anchors:
            word = anchor.get('word', '')
            x = anchor.get('x', 0)
            y = anchor.get('y', 0)
            zh = anchor.get('zh', '')
            csv_lines.append(f"{word},{x},{y},{zh}")

        csv_content = "\n".join(csv_lines)

        # 创建响应
        response = Response(csv_content, mimetype='text/csv')
        filename = f"{lens_id}_anchors_{int(time.time())}.csv"
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"导出失败: {str(e)}"
        }), 500


@app.route('/api/lenses/<lens_id>/anchors/import', methods=['POST'])
def import_anchors(lens_id):
    """
    从 CSV 文件导入锚点

    Form Data:
    - file: CSV 文件
    - mode: 导入模式 (replace/merge/append)

    CSV 格式: word,x,y,zh
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "error": "未上传文件"
            }), 400

        file = request.files['file']
        mode = request.form.get('mode', 'append')  # replace | merge | append

        if mode not in ['replace', 'merge', 'append']:
            return jsonify({
                "success": False,
                "error": f"无效的导入模式: {mode}"
            }), 400

        # 读取 CSV 文件
        import io
        import csv

        stream = io.StringIO(file.read().decode('utf-8'))
        reader = csv.DictReader(stream)

        # 验证 CSV 格式
        if not all(field in reader.fieldnames for field in ['word', 'x', 'y']):
            return jsonify({
                "success": False,
                "error": "CSV 格式错误。必须包含列: word, x, y (可选: zh)"
            }), 400

        # 加载配置
        config = load_config_v2()

        if lens_id not in config:
            return jsonify({
                "success": False,
                "error": f"棱镜 '{lens_id}' 不存在"
            }), 404

        # 保存导入前的快照
        try:
            from lens_history import save_lens_snapshot
            save_lens_snapshot(lens_id, config[lens_id],
                             action="before_import",
                             description=f"导入锚点前 (模式: {mode})")
        except Exception as e:
            print(f"Warning: Failed to save history snapshot: {e}")

        # 根据模式处理锚点
        if mode == 'replace':
            config[lens_id]['anchors'] = []

        imported_count = 0
        updated_count = 0

        for row in reader:
            word = row['word'].strip()
            if not word:
                continue

            new_anchor = {
                'word': word,
                'x': float(row['x']),
                'y': float(row['y']),
                'zh': row.get('zh', '').strip()
            }

            if mode == 'merge':
                # 查找是否已存在相同词的锚点
                existing = next((a for a in config[lens_id]['anchors']
                               if a['word'].lower() == word.lower()), None)
                if existing:
                    existing.update(new_anchor)
                    updated_count += 1
                else:
                    config[lens_id]['anchors'].append(new_anchor)
                    imported_count += 1
            else:  # append or replace
                config[lens_id]['anchors'].append(new_anchor)
                imported_count += 1

        save_config_v2(config)

        return jsonify({
            "success": True,
            "message": f"成功导入 {imported_count} 个锚点" +
                      (f"，更新 {updated_count} 个锚点" if updated_count > 0 else ""),
            "imported_count": imported_count,
            "updated_count": updated_count
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"导入失败: {str(e)}"
        }), 500


# ==========================================
# 棱镜配置导入/导出 API
# ==========================================

@app.route('/api/lenses/<lens_id>/export', methods=['GET'])
def export_lens_config(lens_id):
    """
    导出完整棱镜配置为 JSON 文件
    """
    try:
        config = load_config_v2()

        if lens_id not in config:
            return jsonify({
                "success": False,
                "error": f"棱镜 '{lens_id}' 不存在"
            }), 404

        lens_config = config[lens_id]

        # 添加导出元数据
        export_data = {
            '_export_meta': {
                'lens_id': lens_id,
                'exported_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'version': '3.0'
            },
            'config': lens_config
        }

        # 创建响应
        response = Response(
            json.dumps(export_data, indent=2, ensure_ascii=False),
            mimetype='application/json'
        )
        filename = f"{lens_id}_config_{int(time.time())}.json"
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"导出失败: {str(e)}"
        }), 500


@app.route('/api/lenses/import', methods=['POST'])
def import_lens_config():
    """
    从 JSON 文件导入棱镜配置

    Form Data:
    - file: JSON 文件
    - mode: 导入模式
      - new: 创建新棱镜（必须提供新 ID）
      - replace: 替换现有棱镜
      - merge: 合并到现有棱镜
    - lens_id: (mode=new 时必需) 新棱镜 ID
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "error": "未上传文件"
            }), 400

        file = request.files['file']
        mode = request.form.get('mode', 'new')
        new_lens_id = request.form.get('lens_id', '').strip().lower()

        # 读取 JSON 文件
        import json
        content = json.loads(file.read().decode('utf-8'))

        # 提取配置（兼容带元数据和不带元数据的格式）
        if '_export_meta' in content:
            lens_config = content['config']
            original_id = content['_export_meta']['lens_id']
        else:
            lens_config = content
            original_id = None

        config = load_config_v2()

        if mode == 'new':
            # 创建新棱镜
            if not new_lens_id:
                return jsonify({
                    "success": False,
                    "error": "mode=new 时必须提供 lens_id"
                }), 400

            # 验证 ID
            if not re.match(r'^[a-z][a-z0-9_]*$', new_lens_id):
                return jsonify({
                    "success": False,
                    "error": "ID 格式无效"
                }), 400

            if new_lens_id in RESERVED_IDS:
                return jsonify({
                    "success": False,
                    "error": f"'{new_lens_id}' 是系统保留 ID"
                }), 409

            if new_lens_id in config:
                return jsonify({
                    "success": False,
                    "error": f"棱镜 '{new_lens_id}' 已存在"
                }), 409

            # 保存快照
            try:
                from lens_history import save_lens_snapshot
                save_lens_snapshot(new_lens_id, lens_config,
                                 action="import",
                                 description=f"从 {original_id or '外部'} 导入")
            except Exception as e:
                print(f"Warning: Failed to save history snapshot: {e}")

            config[new_lens_id] = lens_config
            save_config_v2(config)

            return jsonify({
                "success": True,
                "message": f"成功导入为新棱镜 '{new_lens_id}'"
            })

        elif mode == 'replace':
            # 替换现有棱镜
            if not original_id or original_id not in config:
                return jsonify({
                    "success": False,
                    "error": "无法确定要替换的棱镜 ID"
                }), 400

            # 保存快照
            try:
                from lens_history import save_lens_snapshot
                save_lens_snapshot(original_id, config[original_id],
                                 action="before_import_replace",
                                 description="导入替换前的状态")
            except Exception as e:
                print(f"Warning: Failed to save history snapshot: {e}")

            config[original_id] = lens_config
            save_config_v2(config)

            return jsonify({
                "success": True,
                "message": f"成功替换棱镜 '{original_id}'"
            })

        elif mode == 'merge':
            # 合并到现有棱镜
            if not original_id or original_id not in config:
                return jsonify({
                    "success": False,
                    "error": "无法确定要合并的棱镜 ID"
                }), 400

            # 保存快照
            try:
                from lens_history import save_lens_snapshot
                save_lens_snapshot(original_id, config[original_id],
                                 action="before_import_merge",
                                 description="导入合并前的状态")
            except Exception as e:
                print(f"Warning: Failed to save history snapshot: {e}")

            # 合并配置（智能合并锚点）
            existing_config = config[original_id]

            # 合并锚点（不重复）
            existing_words = {a['word'].lower() for a in existing_config.get('anchors', [])}
            for anchor in lens_config.get('anchors', []):
                if anchor['word'].lower() not in existing_words:
                    existing_config.setdefault('anchors', []).append(anchor)

            # 更新其他字段（如果存在）
            for key in ['name', 'description', 'axes']:
                if key in lens_config:
                    existing_config[key] = lens_config[key]

            save_config_v2(config)

            return jsonify({
                "success": True,
                "message": f"成功合并到棱镜 '{original_id}'"
            })

        else:
            return jsonify({
                "success": False,
                "error": f"无效的导入模式: {mode}"
            }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"导入失败: {str(e)}"
        }), 500


# ==========================================
# 历史版本管理 API
# ==========================================

@app.route('/api/lenses/<lens_id>/history', methods=['GET'])
def get_lens_history(lens_id):
    """
    获取棱镜的历史版本列表
    """
    try:
        from lens_history import get_lens_history as get_history

        limit = request.args.get('limit', 20, type=int)
        history = get_history(lens_id, limit=limit)

        return jsonify({
            "success": True,
            "lens_id": lens_id,
            "history": history,
            "count": len(history)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"获取历史失败: {str(e)}"
        }), 500


@app.route('/api/lenses/<lens_id>/restore', methods=['POST'])
def restore_lens_snapshot(lens_id):
    """
    回滚到指定历史版本

    Request Body:
    {
        "filename": "lens_id_2025-01-06T12-30-45.json"
    }
    """
    try:
        from lens_history import restore_lens_snapshot as restore

        data = request.json
        filename = data.get('filename')

        if not filename:
            return jsonify({
                "success": False,
                "error": "未指定快照文件名"
            }), 400

        result = restore(lens_id, filename)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"回滚失败: {str(e)}"
        }), 500


@app.route('/api/lenses/<lens_id>/history/delete', methods=['DELETE'])
def delete_lens_history(lens_id):
    """
    删除棱镜的所有历史版本
    """
    try:
        from lens_history import delete_all_lens_history

        result = delete_all_lens_history(lens_id)

        return jsonify({
            "success": True,
            "message": f"成功删除 {result['deleted_count']} 个历史版本"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"删除历史失败: {str(e)}"
        }), 500

# ==========================================
# 前端模板 (Single Page App)
# ==========================================

HTML_TEMPLATE = r'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Anchor Map Editor v2.0</title>
    <style>
        :root { --bg: #0f172a; --panel: #1e293b; --accent: #8b5cf6; --text: #e2e8f0; }
        * { box-sizing: border-box; }
        body { margin: 0; background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; height: 100vh; display: flex; flex-direction: column; }
        
        header { padding: 15px 20px; background: #020617; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; }
        h1 { margin: 0; font-size: 18px; display: flex; align-items: center; gap: 10px; }
        
        .main-layout { display: flex; flex: 1; overflow: hidden; }
        
        /* 左侧：画布区域 */
        .canvas-area { flex: 1; position: relative; display: flex; justify-content: center; align-items: center; background: #0f172a; background-image: radial-gradient(#334155 1px, transparent 1px); background-size: 20px 20px; }
        
        .map-container { 
            width: 80vh; height: 80vh; 
            background: #1e293b; 
            border: 2px solid #475569; 
            border-radius: 12px; 
            position: relative; 
            box-shadow: 0 20px 50px -12px rgba(0,0,0,0.5); 
        }
        
        /* 轴标签 */
        .axis-label { position: absolute; font-size: 12px; color: #64748b; font-weight: bold; text-transform: uppercase; background: #0f172a; padding: 4px 8px; border-radius: 4px; border: 1px solid #334155; white-space: nowrap; }
        .axis-top { top: -45px; left: 50%; transform: translateX(-50%); }
        .axis-bottom { bottom: -45px; left: 50%; transform: translateX(-50%); }
        .axis-left { left: -85px; top: 50%; transform: translateY(-50%) rotate(-90deg); }
        .axis-right { right: -85px; top: 50%; transform: translateY(-50%) rotate(90deg); }

        /* 锚点 */
        .pin {
            position: absolute;
            transform: translate(-50%, -50%);
            cursor: grab;
            transition: transform 0.1s, box-shadow 0.1s;
            z-index: 10;
        }
        .pin:active { cursor: grabbing; z-index: 20; }
        .pin-dot {
            width: 12px; height: 12px;
            background: var(--accent);
            border: 2px solid #fff;
            border-radius: 50%;
            box-shadow: 0 2px 5px rgba(0,0,0,0.5);
        }
        .pin-label {
            position: absolute;
            top: -20px; left: 50%; transform: translateX(-50%);
            background: rgba(0,0,0,0.8);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            white-space: nowrap;
            pointer-events: none;
        }
        .pin:hover .pin-dot { transform: scale(1.2); background: #a78bfa; }
        
        /* 选中状态 */
        .pin.selected .pin-dot { background: #f43f5e; border-color: #fca5a5; }
        .pin.selected .pin-label { color: #f43f5e; }

        /* 右侧：控制面板 */
        .sidebar { width: 320px; background: var(--panel); border-left: 1px solid #334155; display: flex; flex-direction: column; }
        .tabs { display: flex; border-bottom: 1px solid #334155; }
        .tab { flex: 1; padding: 15px; text-align: center; cursor: pointer; color: #94a3b8; background: #0f172a; font-size: 12px; }
        .tab.active { background: var(--panel); color: #fff; border-bottom: 2px solid var(--accent); }
        .tab-content { display: none; flex: 1; flex-direction: column; overflow: hidden; }
        .tab-content.active { display: flex; }

        .panel-content { flex: 1; overflow-y: auto; padding: 20px; }
        
        .lens-selector { margin-bottom: 20px; }
        select { width: 100%; padding: 10px; background: #0f172a; color: #fff; border: 1px solid #334155; border-radius: 6px; }
        
        .anchor-list { display: flex; flex-direction: column; gap: 8px; }
        .anchor-item { 
            display: flex; align-items: center; gap: 10px; 
            background: #0f172a; padding: 8px; border-radius: 6px; border: 1px solid #334155; 
            cursor: pointer;
        }
        .anchor-item:hover { border-color: var(--accent); }
        .anchor-item.selected { border-color: #f43f5e; background: #2a1015; }
        .anchor-item input { background: transparent; border: none; color: #fff; flex: 1; outline: none; }
        .anchor-coords { font-family: monospace; font-size: 11px; color: #64748b; }
        .btn-del { color: #64748b; cursor: pointer; }
        .btn-del:hover { color: #f43f5e; }
        
        .actions { padding: 20px; border-top: 1px solid #334155; display: flex; flex-direction: column; gap: 10px; }
        button { padding: 12px; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; transition: 0.2s; }
        .btn-primary { background: var(--accent); color: #fff; }
        .btn-primary:hover { filter: brightness(1.1); }
        .btn-sec { background: #334155; color: #fff; }
        .btn-sec:hover { background: #475569; }
        
        .add-bar { display: flex; gap: 5px; margin-bottom: 10px; }
        .add-bar input { flex: 1; padding: 8px; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 4px; }
        
        .status-toast { 
            position: fixed; bottom: 20px; right: 20px; 
            padding: 12px 20px; border-radius: 8px; 
            background: #10b981; color: #fff; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            transform: translateY(100px); transition: 0.3s;
            z-index: 1000;
        }
        .status-toast.show { transform: translateY(0); }
        .status-toast.error { background: #ef4444; }

        /* 分类选择器 */
        .category-selector {
            margin: 10px 0;
            padding: 12px;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 6px;
        }
        .category-selector label {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            color: #94a3b8;
            margin-bottom: 8px;
            cursor: pointer;
        }
        .category-selector label:last-child { margin-bottom: 0; }
        .category-selector input[type="checkbox"] {
            accent-color: var(--accent);
            width: 16px; height: 16px;
        }

        /* 进度条 */
        .rebuild-overlay {
            position: fixed; inset: 0; background: rgba(0,0,0,0.8);
            display: none; flex-direction: column; justify-content: center; align-items: center;
            z-index: 2000; backdrop-filter: blur(4px);
        }
        .rebuild-overlay.show { display: flex; }
        .progress-box { width: 400px; background: #1e293b; padding: 30px; border-radius: 12px; border: 1px solid #334155; }
        .progress-bar-bg { width: 100%; height: 8px; background: #0f172a; border-radius: 4px; margin: 15px 0; overflow: hidden; }
        .progress-bar-fill { width: 0%; height: 100%; background: var(--accent); transition: width 0.3s; }
        .progress-status { font-size: 14px; color: #94a3b8; text-align: center; }

        /* 棱镜管理样式 */
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; font-size: 12px; color: #94a3b8; margin-bottom: 5px; }
        .form-group input, .form-group textarea {
            width: 100%; padding: 8px; background: #0f172a; border: 1px solid #334155;
            color: #fff; border-radius: 4px; font-size: 13px;
        }
        .form-group textarea { resize: vertical; min-height: 60px; }
        .axis-inputs { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .lens-list-item {
            background: #0f172a; padding: 12px; border-radius: 6px; border: 1px solid #334155;
            margin-bottom: 8px; cursor: pointer;
        }
        .lens-list-item:hover { border-color: var(--accent); }
        .lens-list-item h4 { margin: 0 0 5px 0; font-size: 14px; }
        .lens-list-item p { margin: 0; font-size: 11px; color: #64748b; }
        .lens-actions { display: flex; gap: 5px; margin-top: 8px; }
        .btn-sm { padding: 4px 8px; font-size: 11px; }
        .btn-danger { background: #dc2626; color: #fff; }
        .btn-danger:hover { background: #b91c1c; }

        /* 导入/导出样式 */
        .export-buttons { display: flex; flex-direction: column; gap: 10px; }
        .import-section { margin-top: 20px; padding-top: 20px; border-top: 1px solid #334155; }
        .file-input-wrapper { position: relative; overflow: hidden; display: inline-block; width: 100%; }
        .file-input-wrapper input[type=file] {
            position: absolute; left: 0; top: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%;
        }
        .mode-selector { display: flex; gap: 10px; margin: 10px 0; }
        .mode-option {
            flex: 1; padding: 8px; background: #0f172a; border: 1px solid #334155;
            border-radius: 4px; text-align: center; font-size: 12px; cursor: pointer;
        }
        .mode-option.selected { border-color: var(--accent); background: #1e1b4b; }

        /* 历史版本样式 */
        .history-list { max-height: 400px; overflow-y: auto; }
        .history-item {
            background: #0f172a; padding: 10px; border-radius: 6px; border: 1px solid #334155;
            margin-bottom: 8px;
        }
        .history-time { font-size: 13px; color: #fff; margin-bottom: 4px; }
        .history-meta { font-size: 11px; color: #64748b; display: flex; justify-content: space-between; }
        .history-actions { display: flex; gap: 5px; margin-top: 8px; }
        .btn-restore { background: #059669; color: #fff; }
        .btn-restore:hover { background: #047857; }

    </style>
</head>
<body>

<header>
    <h1>📍 Anchor Map Editor <span>v3.0</span></h1>
    <div style="font-size: 12px; color: #64748b;">Project Synesth Core - 动态棱镜管理</div>
</header>

<div class="main-layout">
    <div class="canvas-area">
        <div class="map-container" id="map" ondrop="handleDrop(event)" ondragover="allowDrop(event)">
            <div class="axis-label axis-top" id="label-top">TOP</div>
            <div class="axis-label axis-bottom" id="label-bottom">BOTTOM</div>
            <div class="axis-label axis-left" id="label-left">LEFT</div>
            <div class="axis-label axis-right" id="label-right">RIGHT</div>
            
            <!-- Pins will be rendered here -->
            <div style="position:absolute; inset:0; pointer-events:none; border:1px dashed #334155; opacity:0.3; top:50%; border-width: 1px 0 0 0;"></div>
            <div style="position:absolute; inset:0; pointer-events:none; border:1px dashed #334155; opacity:0.3; left:50%; border-width: 0 0 0 1px;"></div>
        </div>
    </div>
    
    <div class="sidebar">
        <div class="tabs">
            <div class="tab active" onclick="switchTab('anchors')">锚点管理</div>
            <div class="tab" onclick="switchTab('lenses')">棱镜管理</div>
            <div class="tab" onclick="switchTab('io')">导入/导出</div>
            <div class="tab" onclick="switchTab('history')">历史版本</div>
        </div>

        <!-- Tab 1: 锚点管理 -->
        <div id="tab-anchors" class="tab-content active">
            <div class="panel-content">
                <div class="lens-selector">
                    <label style="font-size:12px; color:#64748b; display:block; margin-bottom:5px;">当前编辑棱镜</label>
                    <select id="lensSelect" onchange="switchLens()">
                        <!-- Options populated by JS -->
                    </select>
                </div>

                <div class="add-bar">
                    <input type="text" id="newWord" placeholder="输入新词..." onkeypress="if(event.key==='Enter') addAnchor()">
                    <button class="btn-sec" onclick="addAnchor()" style="padding: 0 15px;">+</button>
                </div>

                <div class="anchor-list" id="anchorList">
                    <!-- List items -->
                </div>
            </div>

            <div class="actions">
                <div class="category-selector">
                    <div style="font-size: 11px; color: #64748b; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em;">过滤词汇类型 (仅对总库生效)</div>
                    <label><input type="checkbox" class="cat-filter" value="adjective" checked> <span>形容词 (Adjectives)</span></label>
                    <label><input type="checkbox" class="cat-filter" value="noun" checked> <span>名词 (Nouns)</span></label>
                    <label><input type="checkbox" class="cat-filter" value="verb" checked> <span>动词 (Verbs)</span></label>
                </div>
                <div style="margin: 15px 0; padding: 12px; background: #0f172a; border-radius: 6px; border: 1px solid #334155;">
                    <label style="display:block; font-size:11px; color:#64748b; margin-bottom:5px;">语义模型选择:</label>
                    <select id="modelSelect" style="width:100%; background:transparent; border:1px solid #475569; color:#fff; border-radius:4px; padding:6px; font-size:12px; outline:none;">
                        <option value="paraphrase-multilingual-MiniLM-L12-v2">Standard (Multi-lingual, Fast)</option>
                        <option value="paraphrase-multilingual-mpnet-base-v2">High Accuracy (Large 模型，较慢)</option>
                        <option value="sentence-transformers/all-MiniLM-L6-v2">Speed focus (English optimized)</option>
                        <option value="shibing624/text2vec-base-chinese">Chinese Optimized (中文增强)</option>
                    </select>
                </div>
                <button class="btn-primary" onclick="rebuildLens()">🚀 保存并重构力场</button>
                <button class="btn-sec" style="margin-top:10px; background:#2563eb;" onclick="syncToCloud()">☁️ 同步到云端 (Supabase)</button>
                <button class="btn-sec" onclick="saveOnly()">💾 仅保存位置</button>
            </div>
        </div>

        <!-- Tab 2: 棱镜管理 -->
        <div id="tab-lenses" class="tab-content">
            <div class="panel-content">
                <button class="btn-primary" onclick="showCreateLensForm()" style="width:100%; margin-bottom:15px;">
                    ➕ 创建新棱镜
                </button>

                <!-- 创建表单 (默认隐藏) -->
                <div id="createLensForm" style="display:none; position:fixed; top:0; left:0; right:0; bottom:0; background:#0f172a; z-index:3000; overflow-y:auto; padding:20px;">
                    <div style="max-width:600px; margin:0 auto; background:#1e293b; padding:25px; border-radius:8px;">
                        <h2 style="margin:0 0 20px 0; font-size:18px; color:#fff;">创建新棱镜</h2>

                        <div class="form-group">
                            <label>棱镜 ID *</label>
                            <input type="text" id="newLensId" placeholder="my_custom_lens" style="font-family:monospace;">
                            <small style="color:#64748b; font-size:11px;">只能包含小写字母、数字、下划线，以字母开头</small>
                        </div>

                        <div class="form-group">
                            <label>棱镜名称 *</label>
                            <input type="text" id="newLensName" placeholder="例如: 力学">
                            <small style="color:#64748b; font-size:11px;">会自动生成格式: "ID / (名称)"</small>
                        </div>

                        <div class="form-group">
                            <label>描述</label>
                            <textarea id="newLensDesc" placeholder="这个棱镜的用途..."></textarea>
                        </div>

                        <div class="form-group">
                            <label>X 轴标签</label>
                            <div class="axis-inputs">
                                <input type="text" id="newLensXNeg" placeholder="例如: Light / (轻)">
                                <input type="text" id="newLensXPos" placeholder="例如: Heavy / (重)">
                            </div>
                            <small style="color:#64748b; font-size:11px;">建议格式: "English / (中文)"</small>
                        </div>

                        <div class="form-group">
                            <label>Y 轴标签</label>
                            <div class="axis-inputs">
                                <input type="text" id="newLensYNeg" placeholder="例如: Dull / (钝)">
                                <input type="text" id="newLensYPos" placeholder="例如: Sharp / (锐)">
                            </div>
                            <small style="color:#64748b; font-size:11px;">建议格式: "English / (中文)"</small>
                        </div>

                        <div class="form-group" style="background:#0f172a; padding:15px; border-radius:6px; border:2px dashed #f59e0b;">
                            <label style="color:#f59e0b; font-size:14px;">✨ 智能功能</label>
                            <div style="font-size:12px; color:#94a3b8; margin-bottom:10px; margin-top:5px;">
                                基于轴标签自动生成 20 个建议锚点（每个象限 5 个）
                            </div>

                            <!-- 词性选择器 -->
                            <div style="margin-bottom:10px;">
                                <label style="font-size:12px; color:#cbd5e1; display:block; margin-bottom:5px;">词性筛选（可选）</label>
                                <select id="posFilterSelect" style="width:100%; padding:8px; background:#1e293b; border:1px solid #334155; border-radius:4px; color:#fff; font-size:12px;">
                                    <option value="">全部词性</option>
                                    <option value="noun">名词 (Noun)</option>
                                    <option value="verb">动词 (Verb)</option>
                                    <option value="adjective" selected>形容词 (Adjective)</option>
                                </select>
                                <small style="color:#64748b; font-size:10px; display:block; margin-top:3px;">
                                    💡 默认推荐形容词，适合描述音质和感受
                                </small>
                            </div>

                            <button class="btn-primary" onclick="generateAnchorsForNewLens()" style="width:100%; font-size:13px; padding:12px;">
                                🎲 生成建议锚点
                            </button>
                            <div id="generatedAnchorsPreview" style="margin-top:10px; font-size:11px; color:#64748b; max-height:80px; overflow-y:auto; background:#020617; padding:10px; border-radius:4px;"></div>
                        </div>

                        <div style="display:flex; gap:10px; margin-top:20px;">
                            <button class="btn-primary" onclick="createNewLens()" style="flex:1; padding:12px; font-size:14px;">创建棱镜</button>
                            <button class="btn-sec" onclick="hideCreateLensForm()" style="flex:1; padding:12px; font-size:14px;">取消</button>
                        </div>
                    </div>
                </div>

                <!-- 编辑表单 (默认隐藏) -->
                <div id="editLensForm" style="display:none; position:fixed; top:0; left:0; right:0; bottom:0; background:#0f172a; z-index:3000; overflow-y:auto; padding:20px;">
                    <div style="max-width:600px; margin:0 auto; background:#1e293b; padding:25px; border-radius:8px;">
                        <h2 style="margin:0 0 20px 0; font-size:18px; color:#fff;">编辑棱镜</h2>
                        <input type="hidden" id="editLensId">

                        <div class="form-group">
                            <label>棱镜 ID</label>
                            <input type="text" id="editLensIdDisplay" disabled style="font-family:monospace; opacity:0.5;">
                            <small style="color:#64748b; font-size:11px;">ID 不可修改</small>
                        </div>

                        <div class="form-group">
                            <label>棱镜名称 *</label>
                            <input type="text" id="editLensName">
                            <small style="color:#64748b; font-size:11px;">格式: "English / 中文" 或 "名称"</small>
                        </div>

                        <div class="form-group">
                            <label>描述</label>
                            <textarea id="editLensDesc" placeholder="这个棱镜的用途..."></textarea>
                        </div>

                        <div class="form-group">
                            <label>X 轴标签</label>
                            <div class="axis-inputs">
                                <input type="text" id="editLensXNeg" placeholder="例如: Dark / (黑暗)">
                                <input type="text" id="editLensXPos" placeholder="例如: Light / (光明)">
                            </div>
                            <small style="color:#64748b; font-size:11px;">建议格式: "English / (中文)"</small>
                        </div>

                        <div class="form-group">
                            <label>Y 轴标签</label>
                            <div class="axis-inputs">
                                <input type="text" id="editLensYNeg" placeholder="例如: Cold / (寒冷)">
                                <input type="text" id="editLensYPos" placeholder="例如: Warm / (温暖)">
                            </div>
                            <small style="color:#64748b; font-size:11px;">建议格式: "English / (中文)"</small>
                        </div>

                        <div style="display:flex; gap:10px; margin-top:20px;">
                            <button class="btn-primary" onclick="saveLensEdit()" style="flex:1; padding:12px; font-size:14px;">保存修改</button>
                            <button class="btn-sec" onclick="hideEditLensForm()" style="flex:1; padding:12px; font-size:14px;">取消</button>
                        </div>
                    </div>
                </div>

                <!-- 棱镜列表 -->
                <div id="lensList">
                    <!-- Populated by JS -->
                </div>
            </div>
        </div>

        <!-- Tab 3: 导入/导出 -->
        <div id="tab-io" class="tab-content">
            <div class="panel-content">
                <h3 style="margin:0 0 15px 0; font-size:14px;">导出</h3>

                <div class="export-buttons">
                    <button class="btn-sec" onclick="exportAnchors()" style="width:100%;">
                        📤 导出锚点 (CSV)
                    </button>
                    <button class="btn-sec" onclick="exportLensConfig()" style="width:100%;">
                        📦 导出棱镜配置 (JSON)
                    </button>
                </div>

                <div class="import-section">
                    <h3 style="margin:0 0 15px 0; font-size:14px;">导入锚点 (CSV)</h3>

                    <div class="file-input-wrapper">
                        <button class="btn-sec" style="width:100%;">📥 选择 CSV 文件</button>
                        <input type="file" id="anchorCsvFile" accept=".csv" onchange="handleAnchorCsvSelect(this)">
                    </div>
                    <div id="selectedAnchorFile" style="font-size:11px; color:#94a3b8; margin:8px 0;"></div>

                    <div style="font-size:11px; color:#64748b; margin:10px 0;">导入模式:</div>
                    <div class="mode-selector">
                        <div class="mode-option selected" onclick="selectImportMode('append', this)" data-mode="append">追加</div>
                        <div class="mode-option" onclick="selectImportMode('merge', this)" data-mode="merge">合并</div>
                        <div class="mode-option" onclick="selectImportMode('replace', this)" data-mode="replace">替换</div>
                    </div>

                    <button class="btn-primary" onclick="importAnchors()" style="width:100%; margin-top:10px;">导入</button>
                </div>

                <div class="import-section">
                    <h3 style="margin:0 0 15px 0; font-size:14px;">导入棱镜配置 (JSON)</h3>

                    <div class="file-input-wrapper">
                        <button class="btn-sec" style="width:100%;">📥 选择 JSON 文件</button>
                        <input type="file" id="lensJsonFile" accept=".json" onchange="handleLensJsonSelect(this)">
                    </div>
                    <div id="selectedLensFile" style="font-size:11px; color:#94a3b8; margin:8px 0;"></div>

                    <div style="font-size:11px; color:#64748b; margin:10px 0;">导入模式:</div>
                    <div class="mode-selector">
                        <div class="mode-option selected" onclick="selectLensImportMode('new', this)" data-mode="new">新建</div>
                        <div class="mode-option" onclick="selectLensImportMode('replace', this)" data-mode="replace">替换</div>
                        <div class="mode-option" onclick="selectLensImportMode('merge', this)" data-mode="merge">合并</div>
                    </div>

                    <div class="form-group" id="newLensIdGroup" style="margin-top:10px;">
                        <label>新棱镜 ID (仅新建模式)</label>
                        <input type="text" id="importLensId" placeholder="my_imported_lens">
                    </div>

                    <button class="btn-primary" onclick="importLensConfig()" style="width:100%; margin-top:10px;">导入</button>
                </div>
            </div>
        </div>

        <!-- Tab 4: 历史版本 -->
        <div id="tab-history" class="tab-content">
            <div class="panel-content">
                <h3 style="margin:0 0 15px 0; font-size:14px;">历史版本</h3>

                <div class="lens-selector">
                    <label style="font-size:12px; color:#64748b; display:block; margin-bottom:5px;">选择棱镜</label>
                    <select id="historyLensSelect" onchange="loadHistory()">
                        <!-- Options populated by JS -->
                    </select>
                </div>

                <div id="historyList" class="history-list">
                    <!-- Populated by JS -->
                </div>

                <button class="btn-danger btn-sm" onclick="deleteLensHistory()" style="width:100%; margin-top:15px;">
                    🗑️ 清空历史
                </button>
            </div>
        </div>
    </div>
</div>

<div id="toast" class="status-toast"></div>

<!-- 进度条弹窗 -->
<div id="rebuildOverlay" class="rebuild-overlay">
    <div class="progress-box">
        <h3 style="margin-top:0; text-align:center;">🚀 正在重构语义力场</h3>
        <div class="progress-bar-bg">
            <div id="progressBar" class="progress-bar-fill"></div>
        </div>
        <div id="progressStatus" class="progress-status">准备中...</div>
    </div>
</div>

<script>
    let config = {};
    let currentLens = 'texture';
    let selectedIndex = -1;
    let isDragging = false;
    
    // 初始化
    async function init() {
        const res = await fetch('/api/config');
        config = await res.json();
        
        const select = document.getElementById('lensSelect');
        select.innerHTML = '';
        Object.keys(config).forEach(key => {
            const opt = document.createElement('option');
            opt.value = key;
            opt.textContent = config[key].name;
            select.appendChild(opt);
        });
        
        switchLens();
    }
    
    function switchLens() {
        currentLens = document.getElementById('lensSelect').value;
        selectedIndex = -1;
        renderMap();
        renderList();
        updateLabels();
    }
    
    function updateLabels() {
        const axes = config[currentLens].axes || {};
        document.getElementById('label-top').textContent = axes.y_label?.pos || 'TOP';
        document.getElementById('label-bottom').textContent = axes.y_label?.neg || 'BOTTOM';
        document.getElementById('label-left').textContent = axes.x_label?.neg || 'LEFT';
        document.getElementById('label-right').textContent = axes.x_label?.pos || 'RIGHT';
    }
    
    function renderMap() {
        const map = document.getElementById('map');
        // Keep grid lines, remove pins
        Array.from(map.children).forEach(c => {
            if(c.classList.contains('pin')) c.remove();
        });
        
        const anchors = config[currentLens].anchors || [];
        anchors.forEach((a, idx) => {
            const pin = document.createElement('div');
            pin.className = `pin ${idx === selectedIndex ? 'selected' : ''}`;
            pin.style.left = `${a.x}%`;
            pin.style.top = `${a.y}%`;
            pin.innerHTML = `
                <div class="pin-label">${a.word} <span style="opacity:0.6; font-size:9px">${a.zh || ''}</span></div>
                <div class="pin-dot"></div>
            `;
            
            // Add click handler for selection
            let mouseDownPos = null;
            pin.onmousedown = (e) => {
                mouseDownPos = { x: e.clientX, y: e.clientY };
                startDrag(e, idx);
            };
            pin.onmouseup = (e) => {
                // If mouse hasn't moved much, treat as click (not drag)
                if (mouseDownPos && 
                    Math.abs(e.clientX - mouseDownPos.x) < 5 && 
                    Math.abs(e.clientY - mouseDownPos.y) < 5) {
                    selectStart(idx);
                }
                mouseDownPos = null;
            };
            
            map.appendChild(pin);
        });
    }
    
    function renderList() {
        const list = document.getElementById('anchorList');
        list.innerHTML = '';
        
        const anchors = config[currentLens].anchors || [];
        anchors.forEach((a, idx) => {
            const item = document.createElement('div');
            item.className = `anchor-item ${idx === selectedIndex ? 'selected' : ''}`;
            item.onclick = () => selectStart(idx);
            item.innerHTML = `
                <div style="flex:1">
                    <input value="${a.word}" onchange="updateWord(${idx}, this.value)" style="width:100%; background:transparent; border:none; color:#fff; outline:none;">
                    ${a.zh ? `<div style="font-size:10px; color:#64748b; margin-top:2px">${a.zh}</div>` : ''}
                </div>
                <span class="anchor-coords">${Math.round(a.x)},${Math.round(a.y)}</span>
                <span class="btn-del" onclick="removeAnchor(${idx}); event.stopPropagation()">×</span>
            `;
            list.appendChild(item);
        });
    }
    
    // 交互逻辑
    function selectStart(idx) {
        selectedIndex = idx;
        renderMap();
        renderList();
        
        // Auto-scroll to selected item in sidebar
        setTimeout(() => {
            const list = document.getElementById('anchorList');
            const items = list.querySelectorAll('.anchor-item');
            if (items[idx]) {
                items[idx].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }, 50);
    }
    
    function startDrag(e, idx) {
        e.stopPropagation();
        selectedIndex = idx;
        
        // Update selection visually without re-rendering (to preserve DOM elements)
        const map = document.getElementById('map');
        const pins = map.querySelectorAll('.pin');
        pins.forEach((p, i) => {
            if (i === idx) {
                p.classList.add('selected');
            } else {
                p.classList.remove('selected');
            }
        });
        
        renderList();
        
        isDragging = true;
        const rect = map.getBoundingClientRect();
        
        function move(e) {
            if(!isDragging) return;
            let x = ((e.clientX - rect.left) / rect.width) * 100;
            let y = ((e.clientY - rect.top) / rect.height) * 100;
            
            x = Math.max(0, Math.min(100, x));
            y = Math.max(0, Math.min(100, y));
            
            config[currentLens].anchors[idx].x = x;
            config[currentLens].anchors[idx].y = y;
            
            // 实时更新 DOM 避免重绘闪烁
            const pin = pins[idx];
            if(pin) {
                pin.style.left = x + '%';
                pin.style.top = y + '%';
            }
        }
        
        function stop() {
            isDragging = false;
            document.removeEventListener('mousemove', move);
            document.removeEventListener('mouseup', stop);
            renderList(); // 更新坐标数值
        }
        
        document.addEventListener('mousemove', move);
        document.addEventListener('mouseup', stop);
    }
    
    function addAnchor() {
        const val = document.getElementById('newWord').value.trim();
        if(!val) return;
        
        // 默认添加到中心
        config[currentLens].anchors.push({ word: val, x: 50, y: 50 });
        document.getElementById('newWord').value = '';
        renderMap();
        renderList();
    }
    
    function removeAnchor(idx) {
        config[currentLens].anchors.splice(idx, 1);
        if(selectedIndex === idx) selectedIndex = -1;
        renderMap();
        renderList();
    }
    
    function updateWord(idx, val) {
        config[currentLens].anchors[idx].word = val;
        renderMap();
    }
    
    async function saveOnly() {
        await fetch('/api/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        showToast('保存成功');
    }
    
    async function rebuildLens() {
        await saveOnly(); // 先保存
        
        // 获取选中的分类
        const checkedCats = Array.from(document.querySelectorAll('.cat-filter:checked')).map(el => el.value);
        if (checkedCats.length === 0) {
            showToast('❌ 请至少选择一个词汇类型', true);
            return;
        }

        const model = document.getElementById('modelSelect').value;
        const overlay = document.getElementById('rebuildOverlay');
        const bar = document.getElementById('progressBar');
        const status = document.getElementById('progressStatus');
        
        overlay.classList.add('show');
        bar.style.width = '0%';
        status.textContent = '初始化请求...';
        
        const categoriesParam = checkedCats.join(',');
        const eventSource = new EventSource(`/api/rebuild_stream/${currentLens}?categories=${categoriesParam}&model=${model}`);
        
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.error) {
                eventSource.close();
                overlay.classList.remove('show');
                showToast('❌ ' + data.error, true);
                return;
            }
            
            if (data.progress) {
                bar.style.width = data.progress + '%';
            }
            
            if (data.status) {
                status.textContent = data.status;
            }
            
            if (data.message) {
                // 完成
                eventSource.close();
                setTimeout(() => {
                    overlay.classList.remove('show');
                    showToast('✅ ' + data.message);
                }, 500);
            }
        };
        
        eventSource.onerror = () => {
            eventSource.close();
            overlay.classList.remove('show');
            showToast('❌ 重构连接中断', true);
        };
    }

    async function syncToCloud() {
        showToast("☁️ 正在推送数据到云端...");
        try {
            const res = await fetch('/api/sync/cloud', { method: 'POST' });
            const result = await res.json();
            if (result.success) {
                const p = result.prisms;
                const c = result.capsules;
                showToast(`✅ 同步成功! 棱镜: ↑${p.uploaded} 胶囊元数据: ${c.synced_count}个`);
            } else {
                showToast(`❌ 同步失败: ${result.error}`, true);
            }
        } catch (error) {
            console.error(error);
            showToast(`❌ 同步出错: ${error}`, true);
        }
    }
    
    function showToast(msg, isError = false) {
        const t = document.getElementById('toast');
        t.textContent = msg;
        t.className = `status-toast show ${isError ? 'error' : ''}`;
        setTimeout(() => t.classList.remove('show'), 3000);
    }

    // ==========================================
    // Tab 切换
    // ==========================================

    function switchTab(tabName) {
        // 隐藏所有 tab 内容
        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
        // 显示选中的 tab
        document.getElementById(`tab-${tabName}`).classList.add('active');

        // 更新 tab 按钮样式
        document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
        event.target.classList.add('active');

        // 如果切换到棱镜管理或历史 tab，刷新列表
        if (tabName === 'lenses') renderLensList();
        if (tabName === 'history') {
            populateHistoryLensSelect();
            loadHistory();
        }
    }

    // ==========================================
    // 棱镜管理
    // ==========================================

    function renderLensList() {
        const list = document.getElementById('lensList');
        list.innerHTML = '';

        Object.keys(config).forEach(lens_id => {
            const lens = config[lens_id];
            const item = document.createElement('div');
            item.className = 'lens-list-item';
            
            // 根据激活状态设置样式
            const isActive = lens.active !== false; // 默认激活
            if (!isActive) {
                item.style.opacity = '0.5';
                item.style.borderStyle = 'dashed';
            }

            const anchorCount = lens.anchors ? lens.anchors.length : 0;
            const statusText = isActive ? '✅ 已启用' : '⏸️ 已禁用';
            const statusColor = isActive ? '#10b981' : '#6b7280';

            item.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <h4 style="margin:0;">${lens.name || lens_id}</h4>
                    <label style="display:flex; align-items:center; gap:6px; cursor:pointer; font-size:11px; color:${statusColor};">
                        <input type="checkbox" ${isActive ? 'checked' : ''} onchange="toggleLensActive('${lens_id}', this.checked)" style="width:14px; height:14px; accent-color:#6366f1;">
                        ${statusText}
                    </label>
                </div>
                <p style="margin:5px 0;">ID: ${lens_id} | ${anchorCount} 个锚点</p>
                <div class="lens-actions">
                    <button class="btn-sm btn-sec" onclick="editLens('${lens_id}')">编辑</button>
                    <button class="btn-sm btn-danger" onclick="confirmDeleteLens('${lens_id}')">删除</button>
                </div>
            `;
            list.appendChild(item);
        });
    }
    
    async function toggleLensActive(lensId, isActive) {
        try {
            const res = await fetch(`/api/lenses/${lensId}/toggle-active`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ active: isActive })
            });
            const result = await res.json();
            
            if (result.success) {
                // 更新本地配置
                config[lensId].active = isActive;
                showToast(result.message);
                renderLensList(); // 重新渲染列表
            } else {
                showToast('❌ ' + result.error, true);
            }
        } catch (e) {
            showToast('❌ 操作失败: ' + e.message, true);
        }
    }

    function showCreateLensForm() {
        document.getElementById('createLensForm').style.display = 'block';
    }

    function hideCreateLensForm() {
        document.getElementById('createLensForm').style.display = 'none';
        // 清空生成的锚点预览
        document.getElementById('generatedAnchorsPreview').innerHTML = '';
        window.generatedAnchorsForNewLens = [];
    }

    // 存储临时生成的锚点
    window.generatedAnchorsForNewLens = [];

    async function generateAnchorsForNewLens() {
        const x_neg = document.getElementById('newLensXNeg').value.trim();
        const x_pos = document.getElementById('newLensXPos').value.trim();
        const y_neg = document.getElementById('newLensYNeg').value.trim();
        const y_pos = document.getElementById('newLensYPos').value.trim();

        if (!x_neg || !x_pos || !y_neg || !y_pos) {
            showToast('❌ 请先填写完整的轴标签', true);
            return;
        }

        // 获取词性筛选选项
        const posFilterSelect = document.getElementById('posFilterSelect');
        const posFilter = posFilterSelect.value;

        const preview = document.getElementById('generatedAnchorsPreview');
        preview.innerHTML = '<div style="text-align:center; color:#f59e0b;">🔄 正在生成锚点...</div>';

        try {
            // 构建轴配置
            const axes = {
                x_label: { neg: x_neg, pos: x_pos },
                y_label: { neg: y_neg, pos: y_pos }
            };

            // 构建请求参数
            const requestBody = {
                count_per_quadrant: 5,
                axes: axes
            };

            // 如果选择了词性筛选，添加到请求中
            if (posFilter) {
                requestBody.pos_filter = [posFilter];
            }

            // 调用生成 API（传递临时轴配置和词性筛选）
            const res = await fetch(`/api/lenses/temp_preview/generate-anchors`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });

            const result = await res.json();

            if (result.success) {
                window.generatedAnchorsForNewLens = result.anchors;

                // 显示预览 - 更紧凑的布局
                let previewHtml = `<div style="color:#10b981; margin-bottom:3px;">✅ ${result.message}</div>`;

                // 显示唯一词汇数量
                if (result.unique_words !== undefined) {
                    previewHtml += `<div style="color:#94a3b8; font-size:10px; margin-bottom:3px;">🎯 唯一词汇: ${result.unique_words} 个（无重复）</div>`;
                }

                previewHtml += '<div style="max-height:50px; overflow-y:auto; font-size:10px; line-height:1.4;">';

                // 只显示前5个，节省空间
                result.anchors.slice(0, 5).forEach(anchor => {
                    const posTag = anchor.pos ? `<span style="color:#64748b; font-size:9px;">[${anchor.pos}]</span>` : '';
                    previewHtml += `<div style="padding:0;">• ${anchor.word} ${posTag}</div>`;
                });

                if (result.anchors.length > 5) {
                    previewHtml += `<div style="color:#64748b;">... 等 ${result.anchors.length} 个</div>`;
                }

                previewHtml += '</div>';
                preview.innerHTML = previewHtml;

                showToast(`✅ ${result.message}`);
            } else {
                preview.innerHTML = `<div style="color:#ef4444;">❌ ${result.error}</div>`;
                showToast(`❌ ${result.error}`, true);
            }
        } catch (error) {
            preview.innerHTML = `<div style="color:#ef4444;">❌ 生成失败: ${error}</div>`;
            showToast(`❌ 生成失败: ${error}`, true);
        }
    }

    async function createNewLens() {
        const lens_id = document.getElementById('newLensId').value.trim().toLowerCase();
        const name = document.getElementById('newLensName').value.trim();
        const description = document.getElementById('newLensDesc').value.trim();
        const x_neg = document.getElementById('newLensXNeg').value.trim();
        const x_pos = document.getElementById('newLensXPos').value.trim();
        const y_neg = document.getElementById('newLensYNeg').value.trim();
        const y_pos = document.getElementById('newLensYPos').value.trim();

        if (!lens_id || !name) {
            showToast('❌ ID 和名称不能为空', true);
            return;
        }

        const data = {
            id: lens_id,
            name: name,
            description: description,
            axes: {
                x_label: { neg: x_neg || 'Left / (负向)', pos: x_pos || 'Right / (正向)' },
                y_label: { neg: y_neg || 'Bottom / (负向)', pos: y_pos || 'Top / (正向)' }
            }
        };

        try {
            const res = await fetch('/api/lenses', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await res.json();

            if (result.success) {
                // 如果有生成的锚点，自动添加
                if (window.generatedAnchorsForNewLens && window.generatedAnchorsForNewLens.length > 0) {
                    try {
                        // 直接更新配置中的锚点
                        config = await (await fetch('/api/config')).json();
                        config[lens_id].anchors = window.generatedAnchorsForNewLens;

                        // 保存配置
                        await fetch('/api/config', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(config)
                        });

                        showToast(`✅ ${result.message}，并添加了 ${window.generatedAnchorsForNewLens.length} 个建议锚点`);
                    } catch (e) {
                        showToast(`✅ ${result.message}（锚点添加失败，请手动添加）`, true);
                    }
                } else {
                    showToast(`✅ ${result.message}`);
                }

                hideCreateLensForm();
                // 重新加载配置
                config = await (await fetch('/api/config')).json();
                renderLensList();
            } else {
                showToast(`❌ ${result.error}`, true);
                if (result.options) {
                    showToast(`建议: ${result.options.join(', ')}`, true);
                }
            }
        } catch (error) {
            showToast(`❌ 创建失败: ${error}`, true);
        }
    }

    async function confirmDeleteLens(lens_id) {
        if (!confirm(`确定要删除棱镜 "${lens_id}" 吗？\n\n注意：胶囊的标签数据将被保留（孤儿标签机制）。`)) {
            return;
        }

        try {
            const res = await fetch(`/api/lenses/${lens_id}`, {
                method: 'DELETE'
            });

            const result = await res.json();

            if (result.success) {
                showToast(`✅ ${result.message}`);
                config = await (await fetch('/api/config')).json();
                renderLensList();
            } else {
                showToast(`❌ ${result.error}`, true);
            }
        } catch (error) {
            showToast(`❌ 删除失败: ${error}`, true);
        }
    }

    function editLens(lens_id) {
        // 显示编辑表单并填充当前数据
        const lens = config[lens_id];

        // 填充所有字段
        document.getElementById('editLensId').value = lens_id;
        document.getElementById('editLensIdDisplay').value = lens_id;
        document.getElementById('editLensName').value = lens.name || '';
        document.getElementById('editLensDesc').value = lens.description || '';

        // 填充轴标签
        if (lens.axes) {
            document.getElementById('editLensXNeg').value = lens.axes.x_label?.neg || '';
            document.getElementById('editLensXPos').value = lens.axes.x_label?.pos || '';
            document.getElementById('editLensYNeg').value = lens.axes.y_label?.neg || '';
            document.getElementById('editLensYPos').value = lens.axes.y_label?.pos || '';
        }

        // 显示编辑表单（全屏模态框）
        document.getElementById('editLensForm').style.display = 'block';
    }

    function hideEditLensForm() {
        document.getElementById('editLensForm').style.display = 'none';
    }

    async function saveLensEdit() {
        const lens_id = document.getElementById('editLensId').value;
        const name = document.getElementById('editLensName').value.trim();
        const description = document.getElementById('editLensDesc').value.trim();
        const x_neg = document.getElementById('editLensXNeg').value.trim();
        const x_pos = document.getElementById('editLensXPos').value.trim();
        const y_neg = document.getElementById('editLensYNeg').value.trim();
        const y_pos = document.getElementById('editLensYPos').value.trim();

        if (!name) {
            showToast('❌ 名称不能为空', true);
            return;
        }

        const data = {
            name: name,
            description: description,
            axes: {
                x_label: { neg: x_neg, pos: x_pos },
                y_label: { neg: y_neg, pos: y_pos }
            }
        };

        try {
            const res = await fetch(`/api/lenses/${lens_id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await res.json();

            if (result.success) {
                showToast(`✅ ${result.message}`);
                hideEditLensForm();
                // 重新加载配置
                config = await (await fetch('/api/config')).json();
                renderLensList();
            } else {
                showToast(`❌ ${result.error}`, true);
            }
        } catch (error) {
            showToast(`❌ 保存失败: ${error}`, true);
        }
    }

    // ==========================================
    // 导入/导出
    // ==========================================

    let anchorImportMode = 'append';
    let lensImportMode = 'new';

    function selectImportMode(mode, element) {
        anchorImportMode = mode;
        element.parentElement.querySelectorAll('.mode-option').forEach(el => el.classList.remove('selected'));
        element.classList.add('selected');
    }

    function selectLensImportMode(mode, element) {
        lensImportMode = mode;
        element.parentElement.querySelectorAll('.mode-option').forEach(el => el.classList.remove('selected'));
        element.classList.add('selected');

        // 显示/隐藏新棱镜 ID 输入框
        const idGroup = document.getElementById('newLensIdGroup');
        if (mode === 'new') {
            idGroup.style.display = 'block';
        } else {
            idGroup.style.display = 'none';
        }
    }

    function handleAnchorCsvSelect(input) {
        const fileName = input.files[0]?.name;
        document.getElementById('selectedAnchorFile').textContent = fileName || '';
    }

    function handleLensJsonSelect(input) {
        const fileName = input.files[0]?.name;
        document.getElementById('selectedLensFile').textContent = fileName || '';
    }

    async function exportAnchors() {
        const url = `/api/lenses/${currentLens}/anchors/export`;
        window.open(url, '_blank');
        showToast('📤 正在导出锚点...');
    }

    async function exportLensConfig() {
        const url = `/api/lenses/${currentLens}/export`;
        window.open(url, '_blank');
        showToast('📦 正在导出棱镜配置...');
    }

    async function importAnchors() {
        const fileInput = document.getElementById('anchorCsvFile');
        if (!fileInput.files.length) {
            showToast('❌ 请选择 CSV 文件', true);
            return;
        }

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('mode', anchorImportMode);

        try {
            const res = await fetch(`/api/lenses/${currentLens}/anchors/import`, {
                method: 'POST',
                body: formData
            });

            const result = await res.json();

            if (result.success) {
                showToast(`✅ ${result.message}`);
                config = await (await fetch('/api/config')).json();
                renderMap();
                renderList();
                fileInput.value = '';
                document.getElementById('selectedAnchorFile').textContent = '';
            } else {
                showToast(`❌ ${result.error}`, true);
            }
        } catch (error) {
            showToast(`❌ 导入失败: ${error}`, true);
        }
    }

    async function importLensConfig() {
        const fileInput = document.getElementById('lensJsonFile');
        if (!fileInput.files.length) {
            showToast('❌ 请选择 JSON 文件', true);
            return;
        }

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('mode', lensImportMode);

        if (lensImportMode === 'new') {
            const newLensId = document.getElementById('importLensId').value.trim().toLowerCase();
            if (!newLensId) {
                showToast('❌ 新建模式需要提供棱镜 ID', true);
                return;
            }
            formData.append('lens_id', newLensId);
        }

        try {
            const res = await fetch('/api/lenses/import', {
                method: 'POST',
                body: formData
            });

            const result = await res.json();

            if (result.success) {
                showToast(`✅ ${result.message}`);
                config = await (await fetch('/api/config')).json();
                fileInput.value = '';
                document.getElementById('selectedLensFile').textContent = '';
            } else {
                showToast(`❌ ${result.error}`, true);
            }
        } catch (error) {
            showToast(`❌ 导入失败: ${error}`, true);
        }
    }

    // ==========================================
    // 历史版本
    // ==========================================

    function populateHistoryLensSelect() {
        const select = document.getElementById('historyLensSelect');
        select.innerHTML = '';
        Object.keys(config).forEach(key => {
            const opt = document.createElement('option');
            opt.value = key;
            opt.textContent = config[key].name || key;
            select.appendChild(opt);
        });
    }

    async function loadHistory() {
        const lens_id = document.getElementById('historyLensSelect').value;
        const list = document.getElementById('historyList');
        list.innerHTML = '<div style="text-align:center; color:#64748b; padding:20px;">加载中...</div>';

        try {
            const res = await fetch(`/api/lenses/${lens_id}/history`);
            const data = await res.json();

            if (data.success) {
                if (data.history.length === 0) {
                    list.innerHTML = '<div style="text-align:center; color:#64748b; padding:20px;">暂无历史版本</div>';
                    return;
                }

                list.innerHTML = '';
                data.history.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'history-item';

                    const time = new Date(item.timestamp).toLocaleString('zh-CN');

                    div.innerHTML = `
                        <div class="history-time">${time}</div>
                        <div class="history-meta">
                            <span>${item.action}</span>
                            <span>${item.description || ''}</span>
                        </div>
                        <div class="history-actions">
                            <button class="btn-sm btn-restore" onclick='restoreSnapshot("${lens_id}", "${item.filename}")'>
                                回滚到此版本
                            </button>
                        </div>
                    `;
                    list.appendChild(div);
                });
            } else {
                list.innerHTML = `<div style="text-align:center; color:#ef4444; padding:20px;">❌ ${data.error}</div>`;
            }
        } catch (error) {
            list.innerHTML = `<div style="text-align:center; color:#ef4444; padding:20px;">❌ 加载失败: ${error}</div>`;
        }
    }

    async function restoreSnapshot(lens_id, filename) {
        if (!confirm('确定要回滚到此版本吗？\n\n当前配置将被覆盖。')) {
            return;
        }

        try {
            const res = await fetch(`/api/lenses/${lens_id}/restore`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename })
            });

            const result = await res.json();

            if (result.success) {
                showToast(`✅ ${result.message}`);
                config = await (await fetch('/api/config')).json();
                loadHistory();
            } else {
                showToast(`❌ ${result.error}`, true);
            }
        } catch (error) {
            showToast(`❌ 回滚失败: ${error}`, true);
        }
    }

    async function deleteLensHistory() {
        const lens_id = document.getElementById('historyLensSelect').value;
        if (!confirm(`确定要清空 "${lens_id}" 的所有历史版本吗？\n\n此操作不可恢复！`)) {
            return;
        }

        try {
            const res = await fetch(`/api/lenses/${lens_id}/history/delete`, {
                method: 'DELETE'
            });

            const data = await res.json();

            if (data.success) {
                showToast(`✅ ${data.message}`);
                loadHistory();
            } else {
                showToast(`❌ ${data.error}`, true);
            }
        } catch (error) {
            showToast(`❌ 删除失败: ${error}`, true);
        }
    }

    init();
</script>

</body>
</html>
'''

if __name__ == '__main__':
    print(f"\n🚀 Anchor Map Editor v2.0 Started at http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=False)
