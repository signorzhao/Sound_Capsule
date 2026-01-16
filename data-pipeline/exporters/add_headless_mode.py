"""
为 main_export.lua 添加无头模式支持

这个脚本会自动修改原始的 Lua 脚本，添加以下功能：
1. 命令行参数检测（通过信号文件）
2. JSON 配置文件读取
3. 跳过 UI 对话框
4. 写入导出结果 JSON
"""

import re
from pathlib import Path


def add_headless_support():
    """为 Lua 脚本添加无头模式"""

    lua_file = Path(__file__).parent.parent / "lua_scripts" / "main_export.lua"

    # 读取原始文件
    with open(lua_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. 在脚本开头添加无头模式全局变量和检测函数
    headless_code = """
-- ============================================
-- 无头模式支持（Synesth 集成）
-- ============================================

-- 无头模式全局变量
local HEADLESS_MODE = false
local HEADLESS_CONFIG = nil
local HEADLESS_OUTPUT_FILE = nil
local HEADLESS_METADATA = {}

-- 检测无头模式（通过信号文件）
function CheckHeadlessMode()
    local temp_dir = os.getenv("TEMP") or "/tmp"
    local signal_file = temp_dir .. "/synesth_headless_signal.txt"

    local file = io.open(signal_file, "r")
    if file then
        HEADLESS_MODE = true
        HEADLESS_CONFIG = file:read("*line")
        HEADLESS_OUTPUT_FILE = file:read("*line")
        file:close()
        os.remove(signal_file)

        reaper.ShowConsoleMsg("=== Synesth 无头模式 ===\\n")
        reaper.ShowConsoleMsg("配置文件: " .. (HEADLESS_CONFIG or "无") .. "\\n")
        return true
    end
    return false
end

-- 解析 JSON 配置文件（简化版）
function ParseHeadlessConfig(filepath)
    local file = io.open(filepath, "r")
    if not file then
        reaper.ShowConsoleMsg("错误: 无法打开配置文件: " .. filepath .. "\\n")
        return nil
    end

    local content = file:read("*all")
    file:close()

    local config = {}

    -- 提取字段（使用字符串匹配）
    local project_name = content:match('"project_name"%s*:%s*"([^"]*)"')
    if project_name then config.project_name = project_name end

    local theme_name = content:match('"theme_name"%s*:%s*"([^"]*)"')
    if theme_name then config.theme_name = theme_name end

    local output_dir = content:match('"output_dir"%s*:%s*"([^"]*)"')
    if output_dir then config.output_dir = output_dir end

    local render_preview = content:match('"render_preview"%s*:%s*(true|false)')
    if render_preview then
        config.render_preview = (render_preview == "true")
    else
        config.render_preview = true
    end

    reaper.ShowConsoleMsg("解析配置:\\n")
    reaper.ShowConsoleMsg("  项目: " .. (config.project_name or "无") .. "\\n")
    reaper.ShowConsoleMsg("  主题: " .. (config.theme_name or "无") .. "\\n")
    reaper.ShowConsoleMsg("  预览: " .. tostring(config.render_preview) .. "\\n")

    return config
end

-- 写入导出结果 JSON
function WriteHeadlessResult(success, capsule_path, metadata, error_msg)
    if not HEADLESS_OUTPUT_FILE then
        return
    end

    local file = io.open(HEADLESS_OUTPUT_FILE, "w")
    if not file then
        reaper.ShowConsoleMsg("错误: 无法写入结果文件\\n")
        return
    end

    file:write("{\\n")
    file:write('  "success": ' .. tostring(success) .. ",\\n")

    if success then
        file:write('  "capsule_path": "' .. (capsule_path or "") .. '"')
        if metadata then
            file:write(',\\n  "metadata": {\\n')
            file:write('    "name": "' .. (metadata.name or "") .. '",\\n')
            file:write('    "project_name": "' .. (metadata.project_name or "") .. '",\\n')
            file:write('    "theme_name": "' .. (metadata.theme_name or "") .. '"\\n')
            file:write('  }')
        else
            file:write(',\\n  "metadata": null')
        end
        file:write(',\\n  "error": null\\n')
    else
        file:write('  "capsule_path": null,\\n')
        file:write('  "metadata": null,\\n')
        file:write('  "error": "' .. (error_msg or "Unknown error") .. '"\\n')
    end

    file:write("}\\n")
    file:close()

    reaper.ShowConsoleMsg("结果已写入: " .. HEADLESS_OUTPUT_FILE .. "\\n")
end

"""

    # 在第一行注释后插入
    content = content.replace(
        "-- 全局变量：控制控制台输出\nlocal ENABLE_CONSOLE = false",
        "-- 全局变量：控制控制台输出\nlocal ENABLE_CONSOLE = false" + headless_code
    )

    # 2. 修改 ShowExportDialog 函数
    old_dialog_pattern = r'function ShowExportDialog\(defaultName\)\s*?-- 使用更友好的对话框格式.*?return name, exportPreview\nend'

    new_dialog_function = '''function ShowExportDialog(defaultName)
    if HEADLESS_MODE then
        -- 无头模式：从配置文件读取
        local config = ParseHeadlessConfig(HEADLESS_CONFIG)
        if not config then
            WriteHeadlessResult(false, nil, nil, "无法读取配置文件")
            return nil, nil
        end

        local name = config.project_name or defaultName
        local exportPreview = config.render_preview

        -- 清理名称
        name = string.gsub(name, "[<>:\\"/\\\\|?*]", "_")
        name = string.gsub(name, "^%.+$", "_")
        name = string.gsub(name, "%s+", "_")

        -- 保存元数据
        HEADLESS_METADATA = {
            project_name = config.project_name or "",
            theme_name = config.theme_name or ""
        }

        return name, exportPreview
    else
        -- 原始 UI 对话框模式
        -- 使用更友好的对话框格式
        -- GetUserInputs(title, num_inputs, captions_csv, retvals_csv)
        local title = "导出胶囊设置"
        local inputs = "胶囊名称 (将用作文件夹和RPP文件名):,导出预览音频 (需要FFmpeg):"
        local defaultValues = defaultName .. ",1"

        local ret, userInputs = reaper.GetUserInputs(title, 2, inputs, defaultValues)

        if not ret then
            -- 用户取消了对话框
            return nil, nil
        end

        -- 解析用户输入（用逗号分隔）
        local name = ""
        local exportPreviewStr = "1"
        local fieldIndex = 1

        for match in string.gmatch(userInputs, "([^,]+)") do
            if fieldIndex == 1 then
                name = match
                -- 移除首尾空白
                name = string.gsub(name, "^%s+", "")
                name = string.gsub(name, "%s+$", "")
            elseif fieldIndex == 2 then
                exportPreviewStr = string.gsub(match, "^%s+", "")
                exportPreviewStr = string.gsub(exportPreviewStr, "%s+$", "")
            end
            fieldIndex = fieldIndex + 1
        end

        -- 如果名称为空，使用默认名称
        if name == "" then
            name = defaultName
        end

        -- 清理名称（移除非法字符，保留中文字符和基本字符）
        name = string.gsub(name, "[<>:\\"/\\\\|?*]", "_")  -- 移除Windows/Unix非法字符
        name = string.gsub(name, "^%.+$", "_")  -- 移除纯点号
        name = string.gsub(name, "%s+", "_")  -- 空格替换为下划线

        -- 解析是否导出预览
        local exportPreview = (exportPreviewStr == "1" or exportPreviewStr == "是" or
                               string.lower(exportPreviewStr) == "yes" or
                               string.lower(exportPreviewStr) == "y" or
                               exportPreviewStr == "true")

        return name, exportPreview
    end
end'''

    # 替换 ShowExportDialog 函数
    # 由于正则表达式匹配多行比较复杂，我们使用更简单的方法
    # 找到函数开始位置
    start_marker = "function ShowExportDialog(defaultName)"
    end_marker = "\nend\n\n-- 导出胶囊的主函数"

    start_idx = content.find(start_marker)
    if start_idx == -1:
        print("错误: 找不到 ShowExportDialog 函数")
        return False

    end_idx = content.find(end_marker, start_idx)
    if end_idx == -1:
        print("错误: 找不到 ShowExportDialog 函数结束位置")
        return False

    # 替换函数
    content = content[:start_idx] + new_dialog_function + "\n" + content[end_idx:]

    # 3. 修改主函数
    old_main = """-- 主函数
function main()
    ExportCapsule()
end

main()"""

    new_main = """-- 主函数
function main()
    -- 检测无头模式
    CheckHeadlessMode()

    if HEADLESS_MODE then
        ENABLE_CONSOLE = true  -- 强制开启日志
    end

    -- 执行导出
    ExportCapsule()
end

main()"""

    content = content.replace(old_main, new_main)

    # 4. 修改 ExportCapsule 函数以保存元数据
    # 找到 ExportCapsule 函数中创建 metadata 的位置
    # 并在最后添加无头模式的结果写入

    # 查找 metadata 创建的部分
    metadata_pattern = r'local metadata = \{.*?project_name = projectName.*?\}'

    # 这个比较复杂，我们在最后添加一个钩子
    # 查找 "reaper.ShowConsoleMsg(\"胶囊导出完成"
    success_marker = "reaper.ShowConsoleMsg(\"胶囊导出完成"

    if success_marker in content:
        # 在成功消息后添加无头模式的结果写入
        success_hook = """

    -- 无头模式：写入结果文件
    if HEADLESS_MODE then
        local capsule_info = {
            name = capsuleName,
            project_name = HEADLESS_METADATA.project_name or projectName,
            theme_name = HEADLESS_METADATA.theme_name or themeName
        }
        WriteHeadlessResult(true, capsulePath, capsule_info, nil)
    end
"""
        content = content.replace(
            success_marker,
            success_marker + success_hook
        )

    # 保存修改后的文件
    output_file = lua_file.parent / "main_export_headless.lua"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✓ 无头模式版本已生成: {output_file}")
    return True


if __name__ == '__main__':
    print("正在为 main_export.lua 添加无头模式支持...\n")
    if add_headless_support():
        print("\n✓ 完成!")
        print("\n使用方法:")
        print("1. 创建信号文件: /tmp/synesth_headless_signal.txt")
        print("   第一行: 配置文件路径")
        print("   第二行: 结果输出文件路径")
        print("2. 在 REAPER 中运行脚本")
        print("3. 脚本会自动读取配置并跳过 UI")
    else:
        print("\n✗ 失败!")
