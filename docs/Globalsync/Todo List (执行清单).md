#### Step 1: 数据库权限开放 (Supabase) 🛡️

_目标：打破数据隔离，允许共享。_

- [ ] **SQL**: 修改 `cloud_capsules` 的 RLS 策略：
    
    - [ ] `CREATE POLICY "Enable read access for all users" ON "public"."cloud_capsules" FOR SELECT USING (true);`
        
    - [ ] 确保 `INSERT/UPDATE/DELETE` 依然限制为 `auth.uid() = user_id`。
        
- [ ] **SQL**: 修改 `storage.objects` 的策略，允许 `public` 读取 `capsule-files` bucket。
    

#### Step 2: 后端同步逻辑升级 (Python) 🧠

_目标：拉取世界，只推自己。_

- [ ] **修改 `sync_service.py`**:
    
    - [ ] 重构 `download_updates()`: 去掉 `eq('user_id', current_user_id)` 的过滤条件。
        
    - [ ] 实现增量游标：`supabase.table(...).select('*').gt('updated_at', last_sync_time).execute()`。
        
    - [ ] 在插入本地 SQLite 时，确保正确保存 `owner_supabase_user_id` 字段。
        
- [ ] **修改 `capsule_api.py`**:
    
    - [ ] 确保 `/api/capsules` 返回的数据包含 `owner_info` (用户名/头像)。
        

#### Step 3: 资产按需加载 (JIT Integration) ⚡

_目标：结合我们刚才讨论的 JIT 方案。_

- [ ] **集成 `SmartActionButton`**:
    
    - [ ] 如果是别人的胶囊，且本地没有 WAV -> 显示“☁️ 获取”。
        
    - [ ] 点击后 -> 触发下载任务 -> 下载到 `{UserConfig.export_dir}/{capsule_folder_name}`。
        
- [ ] **流式预览**:
    
    - [ ] 修改音频播放器，优先使用本地 `.ogg`，如果本地没有，直接使用 `supabase.storage.getPublicUrl()` 进行在线流式播放。
        

#### Step 4: 前端 UI 适配 (React) 🎨

_目标：区分“我的”和“别人的”。_

- [ ] **胶囊卡片更新**:
    
    - [ ] 如果 `!is_mine`，隐藏“删除”和“编辑标签”按钮。
        
    - [ ] 显示作者徽章 (Avatar/Name)。
        
- [ ] **筛选器**:
    
    - [ ] 添加过滤器：`[全部] [我的] [收藏/下载的]`。
        
- [ ] **只读模式**:
    
    - [ ] 如果用户试图编辑别人的胶囊（比如通过 URL 强行进入），后端 API 必须拦截并返回 `403 Forbidden`。