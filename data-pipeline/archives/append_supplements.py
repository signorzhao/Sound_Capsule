#!/usr/bin/env python3
"""
将补充词汇追加到现有词库中
为每个棱镜调整英文描述以适应语义轴
"""

from pathlib import Path

# 各棱镜的语义轴调整规则
# Texture: X轴 Dark/Fear ↔ Light/Healing, Y轴 Realistic/Serious ↔ Playful/Fun
# Source: X轴 Static/Drone ↔ Transient/Impact, Y轴 Organic/Natural ↔ Sci-Fi/Synth
# Materiality: X轴 Close/Dry ↔ Distant/Wet, Y轴 Cold/Reflective ↔ Warm/Absorbent

TEXTURE_SUFFIX_MAP = {
    # 左上：黑暗+写实（电影惊悚）
    "Abstract/Design": "-cinematic-dramatic",
    "Audio_Process/Design": "-professional-studio",
    "Cinematic/Element": "-cinematic-dramatic-serious",
    "Horror/Ambience": "-dark-horror-serious",
    "Horror/General": "-dark-horror-tense",
    # 右上：光明+写实（自然宁静）
    "Modifier/Sonic_Character": "-acoustic-natural",
    # 左下：黑暗+趣味（怪诞故障）
    "Sound_Word/Electronic": "-glitchy-digital-fun",
    "Sound_Word/Friction_Break": "-harsh-weird-fun",
    # 右下：光明+趣味（幻想电玩）
    "Modifier/Mood": "-emotional-mood",
    "Texture/General": "-texture-quality",
}

SOURCE_SUFFIX_MAP = {
    # 左上：静态+有机（环境氛围）
    "Action/Liquid": "-organic-liquid-ambient",
    "Creature/General": "-organic-creature",
    "Nature/Fire": "-organic-fire-ambient",
    "Nature/Fire_Detail": "-organic-fire",
    "Nature/Water": "-organic-water-ambient",
    "Nature/Water_Action": "-organic-water-action",
    "Nature/Wind": "-organic-wind-ambient",
    # 右上：瞬态+有机（物理拟音）
    "Action/Interaction": "-physical-foley-transient",
    "Action/Movement": "-physical-movement-transient",
    "Action/Destruction": "-physical-destruction-impact",
    "Domestic/Bathroom": "-domestic-foley-transient",
    "Domestic/Kitchen": "-kitchen-foley-transient",
    "Domestic/Utility": "-utility-tool-transient",
    "Foley/Item": "-foley-object-transient",
    "Impact/Nuance": "-impact-physical-transient",
    "Sound_Word/Air_Wind": "-organic-air-transient",
    "Sound_Word/Impact_Dull": "-impact-dull-transient",
    "Sound_Word/Liquid_Wet": "-organic-liquid-transient",
    "Sound_Word/Metal_Glass": "-metal-glass-impact-transient",
    "Sports/Action": "-sports-action-transient",
    "Sports/Ball_Game": "-sports-ball-transient",
    "Sports/Equipment": "-sports-equipment-transient",
    "Sports/Gym": "-gym-equipment-transient",
    "Sports/Skate": "-skate-action-transient",
    "Tools/Garden": "-garden-tool-transient",
    "Tools/Workshop": "-workshop-tool-transient",
    # 左下：静态+科幻（引擎/能量）
    "Industrial/Action": "-industrial-mechanical-sustained",
    "Industrial/Components": "-industrial-mechanical-loop",
    "Industrial/Construction": "-industrial-construction-mechanical",
    # 右下：瞬态+科幻（武器/UI）
    "Leisure/Game": "-game-ui-digital-transient",
    "Movement/Action": "-movement-transient",
    "Movement/General": "-movement-whoosh-transient",
    "Vehicles/Action": "-vehicle-action-transient",
    "Vehicles/Maneuver": "-vehicle-maneuver-transient",
    "Vehicles/Part_Detail": "-vehicle-mechanical-transient",
    "Vehicles/Type": "-vehicle-engine-transient",
    "Weapons/Archery": "-weapon-archery-transient",
    "Weapons/Explosive": "-weapon-explosive-transient",
    "Weapons/Firearm": "-weapon-firearm-transient",
}

MATERIALITY_SUFFIX_MAP = {
    # 左上：近+冷硬（工业/临床）
    "Office/Equipment": "-close-metallic-office-cold",
    "Office/Supplies": "-close-office-cold",
    "Urban/Building": "-close-metallic-urban-cold",
    "Urban/Street": "-close-urban-metallic-cold",
    # 右上：远+冷硬（大教堂/峡谷）
    "Ambience/Public": "-vast-public-reverb-cold",
    # 左下：近+暖软（私密/哑房）
    "Domestic/LivingRoom": "-close-domestic-warm-soft",
    "Domestic/Office": "-close-office-warm-soft",
    # 右下：远+暖软（深渊/水下）
    # 中性
    "Modifier/Perspective": "-perspective-modifier",
    "Modifier/Scale": "-scale-size-modifier",
}

def process_supplement(input_file, output_file, suffix_map):
    """处理补充文件，追加到现有词库"""
    
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 读取现有词库
    with open(output_file, 'r', encoding='utf-8') as f:
        existing = f.read()
    
    # 准备追加内容
    append_lines = []
    current_category = ""
    
    for line in lines[1:]:  # 跳过表头
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('# === '):
            current_category = line.replace('# === ', '').replace(' ===', '')
            append_lines.append(f"\n# --- 补充: {current_category} ---")
            continue
        
        parts = line.split(',', 1)
        if len(parts) < 2:
            continue
        
        cn, en = parts[0].strip(), parts[1].strip()
        
        # 获取后缀
        suffix = ""
        for cat_prefix, cat_suffix in suffix_map.items():
            if current_category.startswith(cat_prefix):
                suffix = cat_suffix
                break
        
        # 添加调整后的词条
        new_en = en + suffix
        append_lines.append(f"{cn},{new_en}")
    
    # 追加到文件
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("\n# ========================================")
        f.write(f"\n# 从 Core High Frequency 自动补充")
        f.write("\n# ========================================")
        for line in append_lines:
            f.write(f"\n{line}")
    
    return len([l for l in append_lines if not l.startswith('#') and not l.startswith('\n')])

def main():
    base_path = Path(__file__).parent
    
    print("=== 追加补充词汇到词库 ===\n")
    
    # Texture
    count = process_supplement(
        base_path / "supplement_texture.csv",
        base_path / "lexicon_texture.csv",
        TEXTURE_SUFFIX_MAP
    )
    print(f"Texture: 追加 {count} 个词汇")
    
    # Source
    count = process_supplement(
        base_path / "supplement_source.csv",
        base_path / "lexicon_source.csv",
        SOURCE_SUFFIX_MAP
    )
    print(f"Source: 追加 {count} 个词汇")
    
    # Materiality
    count = process_supplement(
        base_path / "supplement_materiality.csv",
        base_path / "lexicon_materiality.csv",
        MATERIALITY_SUFFIX_MAP
    )
    print(f"Materiality: 追加 {count} 个词汇")
    
    print("\n✅ 完成! 请运行 mapper.py 重新生成向量数据")

if __name__ == "__main__":
    main()


