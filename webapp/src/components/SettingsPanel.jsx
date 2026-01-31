import React, { useState, useEffect } from 'react';
import { open } from '@tauri-apps/plugin-dialog';
import { getAppConfig, saveAppConfig, resetAppConfig } from '../utils/configApi';
import { getApiUrl, setApiBaseFromConfig } from '../utils/apiClient';

/**
 * 设置面板组件
 * 用于管理应用程序配置
 */
function SettingsPanel({ onClose }) {
  const [config, setConfig] = useState({
    reaper_path: '',
    reaper_ip: '',
    export_dir: '',
    username: '',
    language: 'zh-CN',
    api_base_url: ''
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
        language: savedConfig.language || 'zh-CN',
        api_base_url: savedConfig.api_base_url || ''
      });
    } catch (error) {
      showMessage('error', '加载配置失败: ' + error.message);
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
        showMessage('error', '请设置 REAPER 路径或 IP 地址');
        setLoading(false);
        return;
      }

      if (!config.export_dir) {
        showMessage('error', '请设置导出目录');
        setLoading(false);
        return;
      }

      console.log('✓ 配置验证通过，开始保存');

      // 1. 保存到 Tauri 配置
      await saveAppConfig(config);
      setApiBaseFromConfig(config.api_base_url);
      console.log('✓ Tauri 配置已保存');

      // 2. 同时同步到 Python 后端（不需要认证）
      try {
        const response = await fetch(getApiUrl('/api/config/save'), {
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

      showMessage('success', '配置已保存！下次保存胶囊时会自动使用新目录。');
    } catch (error) {
      showMessage('error', '保存配置失败: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const resetConfig = async () => {
    if (confirm('确定要重置所有配置吗？')) {
      setLoading(true);
      try {
        await resetAppConfig();
        setConfig({
          reaper_path: '',
          reaper_ip: '',
          export_dir: '',
          username: '',
          language: 'zh-CN',
          api_base_url: ''
        });
        showMessage('success', '配置已重置');
      } catch (error) {
        showMessage('error', '重置配置失败: ' + error.message);
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
        title: field === 'reaper_path' ? '选择 REAPER 安装目录' : '选择导出目录'
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
        title: '选择 REAPER 可执行文件'
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

  return (
    <div className="settings-panel">
      <div className="settings-header">
        <h2>应用设置</h2>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>

      {message.text && (
        <div className={`message message-${message.type}`}>
          {message.text}
        </div>
      )}

      {loading ? (
        <div className="loading">加载中...</div>
      ) : (
        <div className="settings-content">
          {/* REAPER 配置 */}
          <section className="settings-section">
            <h3>REAPER 配置</h3>

            <div className="form-group">
              <label>REAPER 安装路径</label>
              <div className="input-with-button">
                <input
                  type="text"
                  value={config.reaper_path}
                  onChange={(e) => setConfig({ ...config, reaper_path: e.target.value })}
                  placeholder="/Applications/REAPER.app 或 C:\\Program Files\\REAPER"
                />
                <button onClick={selectDirectory}>选择目录</button>
                <button onClick={selectFile}>选择文件</button>
              </div>
            </div>

            <div className="form-group">
              <label>REAPER IP 地址（可选）</label>
              <input
                type="text"
                value={config.reaper_ip}
                onChange={(e) => setConfig({ ...config, reaper_ip: e.target.value })}
                placeholder="127.0.0.1"
              />
              <small>如果通过网络连接 REAPER，请填写 IP 地址</small>
            </div>
          </section>

          {/* API 服务器（开发/私有部署） */}
          <section className="settings-section">
            <h3>API 服务器</h3>
            <div className="form-group">
              <label>API 服务器地址（可选）</label>
              <input
                type="text"
                value={config.api_base_url}
                onChange={(e) => setConfig({ ...config, api_base_url: e.target.value })}
                placeholder="http://localhost:5002 或 http://192.168.x.x:5002"
              />
              <small>不填则默认连本机 5002；Windows 开发版连「本地部署的服务器」时填该机地址，如 http://192.168.1.100:5002</small>
            </div>
          </section>

          {/* 导出配置 */}
          <section className="settings-section">
            <h3>导出配置</h3>

            <div className="form-group">
              <label>导出目录</label>
              <div className="input-with-button">
                <input
                  type="text"
                  value={config.export_dir}
                  onChange={(e) => setConfig({ ...config, export_dir: e.target.value })}
                  placeholder="/Users/用户名/SoundCapsule/Exports"
                />
                <button onClick={() => selectDirectory('export_dir')}>选择目录</button>
              </div>
            </div>
          </section>

          {/* 用户配置 */}
          <section className="settings-section">
            <h3>用户配置</h3>

            <div className="form-group">
              <label>用户名</label>
              <input
                type="text"
                value={config.username}
                onChange={(e) => setConfig({ ...config, username: e.target.value })}
                placeholder="请输入用户名"
              />
            </div>

            <div className="form-group">
              <label>语言</label>
              <select
                value={config.language}
                onChange={(e) => setConfig({ ...config, language: e.target.value })}
              >
                <option value="zh-CN">简体中文</option>
                <option value="en-US">English</option>
              </select>
            </div>
          </section>

          {/* 操作按钮 */}
          <div className="settings-actions">
            <button className="btn-primary" onClick={saveConfig}>
              保存配置
            </button>
            <button className="btn-secondary" onClick={resetConfig}>
              重置配置
            </button>
            <button className="btn-secondary" onClick={onClose}>
              取消
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
