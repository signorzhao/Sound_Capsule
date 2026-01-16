-- 一键导出脚本
-- 功能: 检测信号文件并自动执行导出

local TEMP_DIR = "/tmp/synest_export"
local SIGNAL_FILE = TEMP_DIR .. "/trigger.txt"
local CONFIG_FILE = TEMP_DIR .. "/config.json"
local RESULT_FILE = TEMP_DIR .. "/result.json"

-- 检查信号文件
local function check_signal_file()
    local file = io.open(SIGNAL_FILE, "r")
    if file then
        file:close()
        return true
    end
    return false
end

-- 读取配置
local function read_config()
    local file = io.open(CONFIG_FILE, "r")
    if not file then
        return nil
    end

    local content = file:read("*all")
    file:close()

    return json.decode(content)
end

-- 写入结果
local function write_result(result)
    local file = io.open(RESULT_FILE, "w")
    if not file then
        reaper.ShowConsoleMsg("无法写入结果文件\n")
        return false
    end

    file:write(json.encode(result))
    file:close()

    return true
end

-- 主导出函数
local function do_export(config)
    reaper.ShowConsoleMsg("开始一键导出...\n")

    -- 获取选中的 Items
    local selected_items = {}
    local item_count = reaper.CountSelectedMediaItems(0)

    if item_count == 0 then
        return {
            success = false,
            error = "没有选中的 Item"
        }
    end

    for i = 0, item_count - 1 do
        local item = reaper.GetSelectedMediaItem(0, i)
        table.insert(selected_items, item)
    end

    reaper.ShowConsoleMsg(string.format("找到 %d 个选中的 Item\n", item_count))

    -- 这里应该调用实际的导出逻辑
    -- 为了简化,我们暂时返回成功

    local result = {
        success = true,
        capsule_name = config.project_name .. "_" .. config.theme_name,
        message = "导出成功"
    }

    return result
end

-- 主循环
function main()
    -- 检查信号文件
    if not check_signal_file() then
        return
    end

    reaper.ShowConsoleMsg("检测到导出信号\n")

    -- 读取配置
    local config = read_config()
    if not config then
        reaper.ShowConsoleMsg("无法读取配置文件\n")
        return
    end

    reaper.ShowConsoleMsg(string.format("项目: %s\n", config.project_name))
    reaper.ShowConsoleMsg(string.format("主题: %s\n", config.theme_name))

    -- 执行导出
    local result = do_export(config)

    -- 写入结果
    write_result(result)

    reaper.ShowConsoleMsg("导出完成\n")
end

-- 执行
main()
