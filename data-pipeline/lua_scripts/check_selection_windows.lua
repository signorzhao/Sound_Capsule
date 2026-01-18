-- [Windows] 快速检查选中 Items 数量
-- 用途: 在导出前快速验证是否有选中的 Items
-- 返回: 写入结果文件到临时目录
-- 注意: 此脚本静默运行，不弹出任何窗口

-- 禁用控制台输出（静默模式）
local function SilentLog(msg)
    -- 不输出任何内容，保持静默
end

-- 获取临时目录
local function GetTempDir()
    local temp = os.getenv("TEMP") or os.getenv("TMP") or "C:\\Temp"
    return temp .. "\\synest_export"
end

local TEMP_DIR = GetTempDir()

-- 写入结果
local function WriteResult(count)
    local result_path = TEMP_DIR .. "\\selection_check.json"
    
    -- 确保目录存在（静默执行）
    os.execute('if not exist "' .. TEMP_DIR .. '" mkdir "' .. TEMP_DIR .. '" >nul 2>&1')
    
    local result_file = io.open(result_path, "w")
    if not result_file then
        result_path = result_path:gsub("\\", "/")
        result_file = io.open(result_path, "w")
    end

    if result_file then
        local content = string.format('{"selected_items": %d}', count)
        result_file:write(content)
        result_file:close()
    end
end

-- 主逻辑（静默执行）
local num_items = reaper.CountSelectedMediaItems(0)
WriteResult(num_items)
