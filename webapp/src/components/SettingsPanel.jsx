import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { open } from '@tauri-apps/plugin-dialog';
import { getAppConfig, saveAppConfig, resetAppConfig } from '../utils/configApi';
import i18n, { configLangToI18n } from '../i18n';
import { useAuth } from '../contexts/AuthContext';
import * as authApi from '../utils/authApi';

/**
 * 设置面板组件
 * 用于管理应用程序配置
 */
function SettingsPanel({ onClose }) {
  const { t } = useTranslation();
  const { user, accessToken, updateUser } = useAuth();
  const [config, setConfig] = useState({
    reaper_path: '',
    reaper_ip: '',
    export_dir: '',
    username: '',
    language: 'zh-CN'
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  // 加载配置
  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const savedConfig = await getAppConfig();
      setConfig({
        reaper_path: savedConfig.reaper_path || '',
        reaper_ip: savedConfig.reaper_ip || '',
        export_dir: savedConfig.export_dir || '',
        username: savedConfig.username || '',
        language: savedConfig.language || 'zh-CN'
      });
    } catch (error) {
      showMessage('error', t('settings.loadConfigFailed') + ': ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async () => {
    console.log('🔧 SettingsPanel.saveConfig 被调用');
    setLoading(true);
    try {
      // 验证必填字段
      if (!config.reaper_path && !config.reaper_ip) {
        showMessage('error', t('settings.setReaperOrIp'));
        setLoading(false);
        return;
      }

      if (!config.export_dir) {
        showMessage('error', t('settings.setExportDir'));
        setLoading(false);
        return;
      }

      console.log('✓ 配置验证通过，开始保存');

      // 1. 保存到 Tauri 配置
      await saveAppConfig(config);
      console.log('✓ Tauri 配置已保存');

      // 1b. 若已登录，尝试同步语言到云端 profiles
      if (user && accessToken && config.language) {
        try {
          await authApi.updateUserProfile(accessToken, { language: config.language });
        } catch (e) {
          console.warn('云端 language 同步失败（可忽略）:', e?.message);
        }
      }

      // 2. 同时同步到 Python 后端（不需要认证）
      try {
        const response = await fetch('http://localhost:5002/api/config/save', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            export_dir: config.export_dir,
            reaper_path: config.reaper_path
          })
        });

        if (response.ok) {
          const result = await response.json();
          console.log('✓ Python 后端配置已同步:', result);
        } else {
          console.warn('⚠ Python 后端配置同步失败，但 Tauri 配置已保存');
        }
      } catch (error) {
        console.warn('⚠ 无法连接到 Python 后端:', error.message);
        // 不阻塞保存流程，因为 Tauri 配置已保存
      }

      showMessage('success', t('settings.configSaved'));
    } catch (error) {
      showMessage('error', t('settings.saveConfigFailed') + ': ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const resetConfig = async () => {
    if (confirm(t('settings.confirmReset'))) {
      setLoading(true);
      try {
        await resetAppConfig();
        setConfig({
          reaper_path: '',
          reaper_ip: '',
          export_dir: '',
          username: '',
          language: 'zh-CN'
        });
        showMessage('success', t('settings.configReset'));
      } catch (error) {
        showMessage('error', t('settings.resetConfigFailed') + ': ' + error.message);
      } finally {
        setLoading(false);
      }
    }
  };

  const selectDirectory = async (field) => {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: field === 'reaper_path' ? t('settings.selectReaperDir') : t('settings.selectExportDirTitle')
      });

      if (selected) {
        setConfig(prev => ({ ...prev, [field]: selected }));
      }
    } catch (error) {
      console.error('选择目录失败:', error);
    }
  };

  const selectFile = async () => {
    try {
      const selected = await open({
        multiple: false,
        title: t('settings.selectReaperFile')
      });

      if (selected) {
        // 如果选择了文件，提取目录路径
        const pathParts = selected.split(/[/\\]/);
        pathParts.pop(); // 移除文件名
        const dirPath = pathParts.join('/');
        setConfig(prev => ({ ...prev, reaper_path: dirPath }));
      }
    } catch (error) {
      console.error('选择文件失败:', error);
    }
  };

  const showMessage = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage({ type: '', text: '' }), 3000);
  };

  const handleLanguageChange = (e) => {
    const newLang = e.target.value;
    setConfig({ ...config, language: newLang });
    i18n.changeLanguage(configLangToI18n(newLang));
  };

  return (
    <div className="settings-panel">
      <div className="settings-header">
        <h2>{t('settings.title')}</h2>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>

      {message.text && (
        <div className={`message message-${message.type}`}>
          {message.text}
        </div>
      )}

      {loading ? (
        <div className="loading">{t('common.loading')}</div>
      ) : (
        <div className="settings-content">
          {/* REAPER 配置 */}
          <section className="settings-section">
            <h3>{t('settings.reaperSection')}</h3>

            <div className="form-group">
              <label>{t('settings.reaperPath')}</label>
              <div className="input-with-button">
                <input
                  type="text"
                  value={config.reaper_path}
                  onChange={(e) => setConfig({ ...config, reaper_path: e.target.value })}
                  placeholder={t('settings.reaperPathPlaceholder')}
                />
                <button onClick={selectDirectory}>{t('settings.selectDir')}</button>
                <button onClick={selectFile}>{t('settings.selectFile')}</button>
              </div>
            </div>

            <div className="form-group">
              <label>{t('settings.reaperIp')}</label>
              <input
                type="text"
                value={config.reaper_ip}
                onChange={(e) => setConfig({ ...config, reaper_ip: e.target.value })}
                placeholder={t('settings.reaperIpPlaceholder')}
              />
              <small>{t('settings.reaperIpHint')}</small>
            </div>
          </section>

          {/* 导出配置 */}
          <section className="settings-section">
            <h3>{t('settings.exportSection')}</h3>

            <div className="form-group">
              <label>{t('settings.exportDir')}</label>
              <div className="input-with-button">
                <input
                  type="text"
                  value={config.export_dir}
                  onChange={(e) => setConfig({ ...config, export_dir: e.target.value })}
                  placeholder={t('settings.exportDirPlaceholder')}
                />
                <button onClick={() => selectDirectory('export_dir')}>{t('settings.selectDir')}</button>
              </div>
            </div>
          </section>

          {/* 用户配置 */}
          <section className="settings-section">
            <h3>{t('settings.userSection')}</h3>

            <div className="form-group">
              <label>{t('settings.username')}</label>
              <input
                type="text"
                value={config.username}
                onChange={(e) => setConfig({ ...config, username: e.target.value })}
                placeholder={t('settings.usernamePlaceholder')}
              />
            </div>

            <div className="form-group">
              <label>{t('settings.language')}</label>
              <select
                value={config.language}
                onChange={handleLanguageChange}
              >
                <option value="zh-CN">{t('settings.languageZh')}</option>
                <option value="en-US">{t('settings.languageEn')}</option>
              </select>
            </div>
          </section>

          {/* 操作按钮 */}
          <div className="settings-actions">
            <button className="btn-primary" onClick={saveConfig}>
              {t('settings.saveConfig')}
            </button>
            <button className="btn-secondary" onClick={resetConfig}>
              {t('settings.resetConfig')}
            </button>
            <button className="btn-secondary" onClick={onClose}>
              {t('common.cancel')}
            </button>
          </div>
        </div>
      )}

      <style jsx>{`
        .settings-panel {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }

        .settings-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
        }

        .settings-header h2 {
          margin: 0;
          color: #333;
        }

        .close-btn {
          background: none;
          border: none;
          font-size: 24px;
          cursor: pointer;
          padding: 0;
          width: 30px;
          height: 30px;
        }

        .settings-content {
          background: white;
          border-radius: 8px;
          padding: 30px;
          width: 600px;
          max-height: 80vh;
          overflow-y: auto;
        }

        .settings-section {
          margin-bottom: 30px;
        }

        .settings-section h3 {
          margin: 0 0 15px 0;
          color: #555;
          font-size: 16px;
          border-bottom: 2px solid #e0e0e0;
          padding-bottom: 10px;
        }

        .form-group {
          margin-bottom: 15px;
        }

        .form-group label {
          display: block;
          margin-bottom: 5px;
          color: #666;
          font-size: 14px;
        }

        .form-group input,
        .form-group select {
          width: 100%;
          padding: 8px 12px;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 14px;
        }

        .form-group small {
          display: block;
          margin-top: 5px;
          color: #999;
          font-size: 12px;
        }

        .input-with-button {
          display: flex;
          gap: 10px;
        }

        .input-with-button input {
          flex: 1;
        }

        .input-with-button button {
          padding: 8px 16px;
          background: #f0f0f0;
          border: 1px solid #ddd;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
        }

        .input-with-button button:hover {
          background: #e0e0e0;
        }

        .settings-actions {
          display: flex;
          gap: 10px;
          margin-top: 30px;
          padding-top: 20px;
          border-top: 1px solid #e0e0e0;
        }

        .btn-primary {
          flex: 1;
          padding: 10px 20px;
          background: #4CAF50;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
        }

        .btn-primary:hover {
          background: #45a049;
        }

        .btn-secondary {
          padding: 10px 20px;
          background: #f0f0f0;
          color: #333;
          border: 1px solid #ddd;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
        }

        .btn-secondary:hover {
          background: #e0e0e0;
        }

        .message {
          padding: 12px;
          border-radius: 4px;
          margin-bottom: 20px;
          font-size: 14px;
        }

        .message-success {
          background: #d4edda;
          color: #155724;
          border: 1px solid #c3e6cb;
        }

        .message-error {
          background: #f8d7da;
          color: #721c24;
          border: 1px solid #f5c6cb;
        }

        .loading {
          text-align: center;
          padding: 50px;
          color: #666;
        }
      `}</style>
    </div>
  );
}

export default SettingsPanel;
