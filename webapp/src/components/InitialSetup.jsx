import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import i18n, { i18nLangToConfig } from '../i18n';
import { FolderOpen, Settings, Check, AlertCircle } from 'lucide-react';
import { open } from '@tauri-apps/plugin-dialog';
import { getAppConfig, saveAppConfig } from '../utils/configApi';
import { LOCAL_API_BASE } from '../utils/apiOrigins';
import './InitialSetup.css';

/**
 * 初始化设置界面
 * 用于首次启动或配置缺失时
 */
export default function InitialSetup({ onComplete }) {
  const { t } = useTranslation();
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
        title: t('settings.selectReaperFile')
      });

      if (selected) {
        setConfig(prev => ({ ...prev, reaper_path: selected }));
      }
    } catch (err) {
      console.error('选择文件失败:', err);
      setError(t('initialSetup.selectFileFailed') + ': ' + err.message);
    }
  };

  // 选择导出目录
  const selectExportDir = async () => {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: t('settings.selectExportDirTitle')
      });

      if (selected) {
        setConfig(prev => ({ ...prev, export_dir: selected }));
      }
    } catch (err) {
      console.error('选择目录失败:', err);
      setError(t('initialSetup.selectDirFailed') + ': ' + err.message);
    }
  };

  // 保存配置
  const handleSave = async () => {
    if (!isValid) {
      setError(t('initialSetup.selectReaperAndExport'));
      return;
    }

    setIsSaving(true);
    setError('');

    try {
      // 1. 保存到 Tauri 配置
      await saveAppConfig({
        reaper_path: config.reaper_path,
        reaper_ip: null,  // 不再需要
        export_dir: config.export_dir,
        username: null,  // 不再需要
        language: i18nLangToConfig(i18n.language) || 'en-US'
      });

      console.log('✅ Tauri 配置保存成功');

      // 2. 🔑 关键修复：同步到 Python 后端
      // 解决初始化后导出目录不更新的问题（后端启动时配置尚不存在）
      try {
        const response = await fetch(`${LOCAL_API_BASE}/config/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            export_dir: config.export_dir,
            reaper_path: config.reaper_path
          })
        });
        
        if (response.ok) {
          console.log('✅ Python 后端配置已同步');
        } else {
          console.warn('⚠️ Python 后端配置同步失败，但 Tauri 配置已保存');
        }
      } catch (e) {
        console.warn('⚠️ 无法连接到 Python 后端:', e.message);
        // 不阻塞保存流程
      }

      console.log('配置保存成功，准备跳转到主界面');

      // 延迟一下让用户看到成功提示
      setTimeout(() => {
        console.log('调用 onComplete 回调');
        onComplete();
      }, 300);
    } catch (err) {
      console.error('保存配置失败:', err);
      setError(t('initialSetup.saveConfigFailed') + ': ' + err.message);
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
          <h1>{t('initialSetup.welcome')}</h1>
          <p>{t('initialSetup.subtitle')}</p>
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
              {t('initialSetup.reaperPath')} <span className="required">*</span>
            </label>
            <div className="input-group">
              <input
                type="text"
                className="form-input"
                placeholder={t('initialSetup.reaperPathPlaceholder')}
                value={config.reaper_path}
                onChange={(e) => setConfig({ ...config, reaper_path: e.target.value })}
              />
              <button
                className="input-button"
                onClick={selectReaperPath}
                title={t('initialSetup.selectFile')}
              >
                <FolderOpen size={18} />
              </button>
            </div>
            <small className="form-hint">{t('initialSetup.reaperPathHint')}</small>
          </div>

          {/* 导出目录 */}
          <div className="form-group">
            <label className="form-label">
              {t('initialSetup.exportDir')} <span className="required">*</span>
            </label>
            <div className="input-group">
              <input
                type="text"
                className="form-input"
                placeholder={t('initialSetup.exportDirPlaceholder')}
                value={config.export_dir}
                onChange={(e) => setConfig({ ...config, export_dir: e.target.value })}
              />
              <button
                className="input-button"
                onClick={selectExportDir}
                title={t('initialSetup.selectDir')}
              >
                <FolderOpen size={18} />
              </button>
            </div>
            <small className="form-hint">{t('initialSetup.exportDirHint')}</small>
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
              <>{t('common.saving')}</>
            ) : (
              <>
                <Check size={20} />
                {t('initialSetup.saveAndStart')}
              </>
            )}
          </button>
        </div>

        {/* 提示信息 */}
        <div className="setup-footer">
          <p>{t('initialSetup.tip')}</p>
        </div>
      </div>
    </div>
  );
}
