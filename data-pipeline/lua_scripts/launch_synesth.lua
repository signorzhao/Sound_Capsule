-- 从 REAPER 启动 Synesth 导出
-- 功能: 选中 Items 后按快捷键,自动打开 Synesth 并传递项目信息

local TEMP_DIR = "/tmp/synest_export"
local CONFIG_FILE = TEMP_DIR .. "/reaper_trigger.json"

function main()
    -- 检查是否有选中的 Items
    local item_count = reaper.CountSelectedMediaItems(0)

    if item_count == 0 then
        reaper.ShowMessageBox(
            "请先选中要导出的音频 Items",
            "未选中 Items",
            0
        )
        return
    end

    -- 创建临时目录
    local os_command = io.popen("mkdir -p " .. TEMP_DIR)
    os_command:close()

    -- 获取项目信息
    local _, project_path = reaper.EnumProjects(-1, "")
    local project_name = ""

    if project_path ~= "" then
        -- 从路径中提取项目名
        project_name = string.match(project_path, "([^/]+)%.RPP$")
        if not project_name then
            project_name = "未命名项目"
        end
    else
        project_name = "未保存项目"
    end

    -- 准备配置
    local config = {
        project_path = project_path,
        project_name = project_name,
        item_count = item_count,
        timestamp = os.time(),
        trigger_source = "reaper_hotkey"
    }

    -- 写入配置文件
    local file = io.open(CONFIG_FILE, "w")
    if file then
        file:write('{"project_name":"' .. project_name .. '","item_count":' .. item_count .. ',"trigger":"reaper"}')
        file:close()

        reaper.ShowConsoleMsg("✓ 已准备导出配置\n")
        reaper.ShowConsoleMsg("  项目: " .. project_name .. "\n")
        reaper.ShowConsoleMsg("  Items: " .. item_count .. "\n\n")
    else
        reaper.ShowMessageBox("无法写入配置文件", "错误", 0)
        return
    end

    -- 打开 Synesth
    local synesth_url = "http://localhost:5173?source=reaper&import=auto"

    -- 使用系统默认浏览器打开
    local os_type = reaper.GetOS()

    local cmd = ""
    if os_type == "OSX64" or os_type == "macOS" or os_type == "OSX32" then
        -- macOS
        cmd = "open \"" .. synesth_url .. "\""
    elseif os_type == "Win32" or os_type == "Win64" then
        -- Windows
        cmd = "cmd /c start \"\" \"" .. synesth_url .. "\""
    else
        -- Linux
        cmd = "xdg-open \"" .. synesth_url .. "\""
    end

    -- 执行命令
    local result = os.execute(cmd)

    reaper.ShowConsoleMsg("执行命令: " .. cmd .. "\n")
    reaper.ShowConsoleMsg("结果: " .. tostring(result) .. "\n\n")

    reaper.ShowMessageBox(
        "已尝试打开 Synesth\n\n" ..
        "选中了 " .. item_count .. " 个 Items\n" ..
        "项目: " .. project_name .. "\n\n" ..
        "如果浏览器没有自动打开,\n" ..
        "请手动访问: " .. synesth_url,
        "已启动 Synesth",
        0
    )
end

-- 执行
main()
