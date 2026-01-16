import React, { useState, useEffect } from 'react';
import { FolderOpen, Settings, Check, AlertCircle } from 'lucide-react';
import { open } from '@tauri-apps/plugin-dialog';
import { getAppConfig, saveAppConfig } from '../utils/configApi';
import './InitialSetup.css';

/**
 * 初始化设置界面
 * 用于首次启动或配置缺失时
 */
export default function InitialSetup({ onComplete }) {
  const [config, setConfig] = useState({
    reaper_path: '',
    export_dir: '',
    reaper_ip: '',
    username: ''
  });
  const [isValid, setIsValid] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  // 加载现有配置
  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const saved = await getAppConfig();
      setConfig({
        reaper_path: saved.reaper_path || '',
        export_dir: saved.export_dir || '',
        reaper_ip: saved.reaper_ip || '',
        username: saved.username || ''
      });
    } catch (err) {
      console.error('加载配置失败:', err);
    }
  };

  // 验证配置（需要导出目录和 REAPER 路径）
  useEffect(() => {
    const valid = config.reaper_path.trim() !== '' && config.export_dir.trim() !== '';
    setIsValid(valid);
    setError('');
  }, [config]);

  // 选择 REAPER 路径
  const selectReaperPath = async () => {
    try {
      const selected = await open({
        directory: false,
        multiple: false,
        title: '选择 REAPER 可执行文件'
      });

      if (selected) {
        setConfig(prev => ({ ...prev, reaper_path: selected }));
      }
    } catch (err) {
      console.error('选择文件失败:', err);
      setError('选择文件失败: ' + err.message);
    }
  };

  // 选择导出目录
  const selectExportDir = async () => {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: '选择导出目录'
      });

      if (selected) {
        setConfig(prev => ({ ...prev, export_dir: selected }));
      }
    } catch (err) {
      console.error('选择目录失败:', err);
      setError('选择目录失败: ' + err.message);
    }
  };

  // 保存配置
  const handleSave = async () => {
    if (!isValid) {
      setError('请选择 REAPER 路径和导出目录');
      return;
    }

    setIsSaving(true);
    setError('');

    try {
      await saveAppConfig({
        reaper_path: config.reaper_path,
        reaper_ip: null,  // 不再需要
        export_dir: config.export_dir,
        username: null,  // 不再需要
        language: 'zh-CN'
      });

      console.log('配置保存成功，准备跳转到主界面');

      // 延迟一下让用户看到成功提示
      setTimeout(() => {
        console.log('调用 onComplete 回调');
        onComplete();
      }, 300);
    } catch (err) {
      console.error('保存配置失败:', err);
      setError('保存配置失败: ' + err.message);
      setIsSaving(false);
    }
  };

  return (
    <div className="initial-setup-overlay">
      <div className="initial-setup-modal">
        {/* 头部 */}
        <div className="setup-header">
          <div className="setup-icon">
            <Settings size={32} />
          </div>
          <h1>欢迎来到 Sound Capsule</h1>
          <p>首次使用需要配置基本设置</p>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="setup-error">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {/* 表单 */}
        <div className="setup-form">
          {/* REAPER 路径 */}
          <div className="form-group">
            <label className="form-label">
              REAPER 路径 <span className="required">*</span>
            </label>
            <div className="input-group">
              <input
                type="text"
                className="form-input"
                placeholder="/Applications/REAPER.app 或 C:\\Program Files\\REAPER\\reaper.exe"
                value={config.reaper_path}
                onChange={(e) => setConfig({ ...config, reaper_path: e.target.value })}
              />
              <button
                className="input-button"
                onClick={selectReaperPath}
                title="选择文件"
              >
                <FolderOpen size={18} />
              </button>
            </div>
            <small className="form-hint">选择 REAPER 可执行文件的位置</small>
          </div>

          {/* 导出目录 */}
          <div className="form-group">
            <label className="form-label">
              导出目录 <span className="required">*</span>
            </label>
            <div className="input-group">
              <input
                type="text"
                className="form-input"
                placeholder="/Users/username/SoundCapsule/Exports"
                value={config.export_dir}
                onChange={(e) => setConfig({ ...config, export_dir: e.target.value })}
              />
              <button
                className="input-button"
                onClick={selectExportDir}
                title="选择目录"
              >
                <FolderOpen size={18} />
              </button>
            </div>
            <small className="form-hint">胶囊导出文件的保存位置</small>
          </div>

        </div>

        {/* 底部按钮 */}
        <div className="setup-actions">
          <button
            className={`save-button ${isValid ? 'valid' : ''}`}
            onClick={handleSave}
            disabled={!isValid || isSaving}
          >
            {isSaving ? (
              <>保存中...</>
            ) : (
              <>
                <Check size={20} />
                保存并开始
              </>
            )}
          </button>
        </div>

        {/* 提示信息 */}
        <div className="setup-footer">
          <p>💡 提示：这些设置可以随时在应用设置中修改</p>
        </div>
      </div>
    </div>
  );
}
