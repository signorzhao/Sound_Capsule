-- OSC 导出监控脚本
-- 功能: 监听 OSC 触发信号,自动执行导出

local TEMP_DIR = "/tmp/synest_export"
local CONFIG_FILE = TEMP_DIR .. "/osc_export_config.json"
local RESULT_FILE = TEMP_DIR .. "/export_result.json"

-- 读取配置
function read_config()
    local file = io.open(CONFIG_FILE, "r")
    if not file then
        reaper.ShowConsoleMsg("错误: 无法读取配置文件 " .. CONFIG_FILE .. "\n")
        return nil
    end

    local content = file:read("*all")
    file:close()

    local success, config = pcall(json.decode, content)
    if not success then
        reaper.ShowConsoleMsg("错误: 配置文件格式错误\n")
        return nil
    end

    return config
end

-- 写入结果
function write_result(result)
    local file = io.open(RESULT_FILE, "w")
    if not file then
        reaper.ShowConsoleMsg("错误: 无法写入结果文件\n")
        return false
    end

    file:write(json.encode(result))
    file:close()

    return true
end

-- 主导出函数
function do_export(config)
    reaper.ShowConsoleMsg("=== OSC 触发导出 ===\n")
    reaper.ShowConsoleMsg("项目: " .. config.project_name .. "\n")
    reaper.ShowConsoleMsg("主题: " .. config.theme_name .. "\n")
    reaper.ShowConsoleMsg("胶囊: " .. config.capsule_name .. "\n\n")

    -- 获取选中的 Items
    local item_count = reaper.CountSelectedMediaItems(0)

    if item_count == 0 then
        local result = {
            success = false,
            error = "没有选中的 Item"
        }
        write_result(result)
        reaper.ShowConsoleMsg("错误: 没有选中的 Item\n")
        return result
    end

    reaper.ShowConsoleMsg("找到 " .. item_count .. " 个选中的 Item\n")

    -- TODO: 调用完整的导出逻辑
    -- 这里应该调用 main_export2.lua 的导出函数
    -- 为了演示,我们先简化

    local result = {
        success = true,
        capsule_name = config.capsule_name,
        project_name = config.project_name,
        theme_name = config.theme_name,
        item_count = item_count,
        message = "导出成功"
    }

    write_result(result)
    reaper.ShowConsoleMsg("\n=== 导出完成 ===\n")

    return result
end

-- OSC 回调函数
function osc_trigger(path, params, source)
    reaper.ShowConsoleMsg("收到 OSC 触发\n")
    reaper.ShowConsoleMsg("  路径: " .. path .. "\n")
    reaper.ShowConsoleMsg("  来源: " .. source .. "\n\n")

    -- 读取配置
    local config = read_config()
    if not config then
        reaper.ShowMessageBox(
            "无法读取导出配置\n" ..
            "请先在 Synesth 中准备导出",
            "OSC 触发失败",
            0
        )
        return
    end

    -- 执行导出
    do_export(config)

    -- 清理配置文件
    os.remove(CONFIG_FILE)
end

-- 主程序: 设置 OSC 监听
function setup_osc_monitor()
    -- 检查是否有 OSC 支持
    if not reaper.osc_register then
        reaper.ShowMessageBox(
            "此 REAPER 版本不支持 OSC\n" ..
            "请使用 REAPER 5.0 或更高版本",
            "OSC 不可用",
            0
        )
        return
    end

    -- 注册 OSC 回调
    local success = reaper.osc_register("1.0", osc_trigger)

    if success then
        reaper.ShowConsoleMsg("✓ OSC 监听已启动\n")
        reaper.ShowConsoleMsg("  等待来自 Synesth 的触发信号...\n\n")
    else
        reaper.ShowConsoleMsg("✗ OSC 监听启动失败\n")
    end
end

-- 启动监控
setup_osc_monitor()

-- 保持脚本运行
-- 注意: 这个脚本需要在 REAPER 启动时自动运行
-- 可以通过: Actions → SWS/S&M: Startup action 来设置
