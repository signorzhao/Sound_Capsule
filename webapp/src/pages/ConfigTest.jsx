import React, { useState, useEffect } from 'react';
import { getAppConfig, saveAppConfig, resetAppConfig, getDefaultConfig } from '../utils/configApi';
import { invoke } from '@tauri-apps/api/core';

/**
 * 配置管理测试页面
 */
function ConfigTest() {
  const [config, setConfig] = useState(getDefaultConfig());
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [appPaths, setAppPaths] = useState(null);

  // 加载配置
  const handleLoad = async () => {
    setStatus('加载中...');
    setError('');
    try {
      const loadedConfig = await getAppConfig();
      setConfig(loadedConfig);
      setStatus('✅ 配置加载成功！');
      console.log('加载的配置:', loadedConfig);
    } catch (err) {
      setError('❌ 加载失败: ' + err.message);
      setStatus('');
    }
  };

  // 保存配置
  const handleSave = async () => {
    setStatus('保存中...');
    setError('');
    try {
      await saveAppConfig(config);
      setStatus('✅ 配置保存成功！');
      console.log('保存的配置:', config);
    } catch (err) {
      setError('❌ 保存失败: ' + err.message);
      setStatus('');
    }
  };

  // 重置配置
  const handleReset = async () => {
    if (!confirm('确定要重置所有配置吗？')) return;

    setStatus('重置中...');
    setError('');
    try {
      await resetAppConfig();
      const defaultConfig = getDefaultConfig();
      setConfig(defaultConfig);
      setStatus('✅ 配置已重置！');
    } catch (err) {
      setError('❌ 重置失败: ' + err.message);
      setStatus('');
    }
  };

  // 页面加载时自动读取配置
  useEffect(() => {
    handleLoad();
    handleGetPaths(); // 自动获取路径
  }, []);

  // 获取应用路径
  const handleGetPaths = async () => {
    setStatus('正在获取应用路径...');
    setError('');
    try {
      const paths = await invoke('get_app_paths');
      setAppPaths(paths);
      setStatus('✅ 路径获取成功！');
      console.log('应用路径:', paths);
    } catch (err) {
      setError('❌ 获取路径失败: ' + err.message);
      setStatus('');
      console.error('路径获取错误:', err);
    }
  };

  return (
    <div style={{
      padding: '40px',
      maxWidth: '800px',
      margin: '0 auto',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      backgroundColor: '#ffffff',
      color: '#333333',
      minHeight: '100vh'
    }}>
      <h1 style={{ marginBottom: '30px', color: '#000000' }}>🧪 配置管理测试</h1>

      {/* 状态消息 */}
      {status && (
        <div style={{
          padding: '12px',
          marginBottom: '20px',
          backgroundColor: '#d4edda',
          color: '#155724',
          border: '1px solid #c3e6cb',
          borderRadius: '4px',
          fontWeight: '500'
        }}>
          {status}
        </div>
      )}

      {error && (
        <div style={{
          padding: '12px',
          marginBottom: '20px',
          backgroundColor: '#f8d7da',
          color: '#721c24',
          border: '1px solid #f5c6cb',
          borderRadius: '4px',
          fontWeight: '500'
        }}>
          {error}
        </div>
      )}

      {/* 配置表单 */}
      <div style={{
        background: '#ffffff',
        padding: '30px',
        borderRadius: '8px',
        marginBottom: '20px',
        border: '1px solid #e0e0e0',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
      }}>
        <h2 style={{ marginTop: 0, marginBottom: '20px', color: '#000000' }}>当前配置</h2>

        {/* REAPER 路径 */}
        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', color: '#333333' }}>
            REAPER 路径:
          </label>
          <input
            type="text"
            value={config.reaper_path || ''}
            onChange={(e) => setConfig({ ...config, reaper_path: e.target.value })}
            placeholder="/Applications/REAPER.app"
            style={{
              width: '100%',
              padding: '10px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px',
              color: '#333333',
              backgroundColor: '#ffffff'
            }}
          />
        </div>

        {/* REAPER IP */}
        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', color: '#333333' }}>
            REAPER IP 地址:
          </label>
          <input
            type="text"
            value={config.reaper_ip || ''}
            onChange={(e) => setConfig({ ...config, reaper_ip: e.target.value })}
            placeholder="127.0.0.1"
            style={{
              width: '100%',
              padding: '10px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px',
              color: '#333333',
              backgroundColor: '#ffffff'
            }}
          />
        </div>

        {/* 导出目录 */}
        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', color: '#333333' }}>
            导出目录:
          </label>
          <input
            type="text"
            value={config.export_dir || ''}
            onChange={(e) => setConfig({ ...config, export_dir: e.target.value })}
            placeholder="/Users/username/SoundCapsule/Exports"
            style={{
              width: '100%',
              padding: '10px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px',
              color: '#333333',
              backgroundColor: '#ffffff'
            }}
          />
        </div>

        {/* 用户名 */}
        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', color: '#333333' }}>
            用户名:
          </label>
          <input
            type="text"
            value={config.username || ''}
            onChange={(e) => setConfig({ ...config, username: e.target.value })}
            placeholder="请输入用户名"
            style={{
              width: '100%',
              padding: '10px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px',
              color: '#333333',
              backgroundColor: '#ffffff'
            }}
          />
        </div>

        {/* 语言 */}
        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', color: '#333333' }}>
            语言:
          </label>
          <select
            value={config.language || 'zh-CN'}
            onChange={(e) => setConfig({ ...config, language: e.target.value })}
            style={{
              width: '100%',
              padding: '10px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px',
              color: '#333333',
              backgroundColor: '#ffffff'
            }}
          >
            <option value="zh-CN">简体中文</option>
            <option value="en-US">English</option>
          </select>
        </div>
      </div>

      {/* 操作按钮 */}
      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
        <button
          onClick={handleSave}
          style={{
            padding: '12px 24px',
            backgroundColor: '#4CAF50',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 'bold'
          }}
        >
          💾 保存配置
        </button>

        <button
          onClick={handleLoad}
          style={{
            padding: '12px 24px',
            backgroundColor: '#2196F3',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 'bold'
          }}
        >
          🔄 重新加载
        </button>

        <button
          onClick={handleReset}
          style={{
            padding: '12px 24px',
            backgroundColor: '#f44336',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 'bold'
          }}
        >
          🗑️ 重置配置
        </button>

        <button
          onClick={handleGetPaths}
          style={{
            padding: '12px 24px',
            backgroundColor: '#9C27B0',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 'bold'
          }}
        >
          🛤️ 测试路径
        </button>
      </div>

      {/* 配置预览 */}
      <div style={{
        marginTop: '30px',
        padding: '20px',
        background: '#fff',
        border: '1px solid #ddd',
        borderRadius: '8px'
      }}>
        <h3 style={{ marginTop: 0 }}>配置 JSON 预览</h3>
        <pre style={{
          background: '#f5f5f5',
          padding: '15px',
          borderRadius: '4px',
          overflow: 'auto',
          fontSize: '13px'
        }}>
          {JSON.stringify(config, null, 2)}
        </pre>
      </div>

      {/* 测试步骤说明 */}
      <div style={{
        marginTop: '30px',
        padding: '20px',
        background: '#e3f2fd',
        borderRadius: '8px'
      }}>
        <h3 style={{ marginTop: 0 }}>📋 测试步骤</h3>
        <ol style={{ lineHeight: '1.8' }}>
          <li>修改上面的配置值</li>
          <li>点击"保存配置"按钮</li>
          <li>检查控制台输出，确认保存成功</li>
          <li>刷新页面（配置应该自动加载）</li>
          <li>验证配置值是否正确恢复</li>
          <li>点击"重置配置"测试重置功能</li>
        </ol>
      </div>

      {/* 路径信息展示 */}
      {appPaths && (
        <div style={{
          marginTop: '30px',
          padding: '20px',
          background: '#f3e5f5',
          border: '2px solid #9C27B0',
          borderRadius: '8px'
        }}>
          <h3 style={{ marginTop: 0, color: '#6A1B9A' }}>🛤️ 应用路径信息</h3>
          <div style={{
            background: '#ffffff',
            padding: '15px',
            borderRadius: '4px',
            marginTop: '15px'
          }}>
            <div style={{ marginBottom: '10px' }}>
              <strong>📁 应用数据目录:</strong><br />
              <code style={{ color: '#9C27B0', wordBreak: 'break-all' }}>{appPaths.app_data_dir}</code>
            </div>
            <div style={{ marginBottom: '10px' }}>
              <strong>📦 资源目录:</strong><br />
              <code style={{ color: '#9C27B0', wordBreak: 'break-all' }}>{appPaths.resources_dir}</code>
            </div>
            <div style={{ marginBottom: '10px' }}>
              <strong>📜 脚本目录 (Lua):</strong><br />
              <code style={{ color: '#9C27B0', wordBreak: 'break-all' }}>{appPaths.scripts_dir}</code>
            </div>
            <div style={{ marginBottom: '10px' }}>
              <strong>🐍 Python 环境目录:</strong><br />
              <code style={{ color: '#9C27B0', wordBreak: 'break-all' }}>{appPaths.python_env_dir}</code>
            </div>
            <div>
              <strong>🗂️ 临时目录:</strong><br />
              <code style={{ color: '#9C27B0', wordBreak: 'break-all' }}>{appPaths.temp_dir}</code>
            </div>
          </div>

          <div style={{ marginTop: '15px', padding: '10px', background: '#e1bee7', borderRadius: '4px' }}>
            <h4 style={{ margin: '0 0 10px 0' }}>完整 JSON:</h4>
            <pre style={{
              background: '#ffffff',
              padding: '10px',
              borderRadius: '4px',
              overflow: 'auto',
              fontSize: '12px',
              margin: 0
            }}>
              {JSON.stringify(appPaths, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {/* 配置文件位置说明 */}
      <div style={{
        marginTop: '20px',
        padding: '20px',
        background: '#fff3e0',
        borderRadius: '8px'
      }}>
        <h3 style={{ marginTop: 0 }}>📂 配置文件位置</h3>
        <ul style={{ lineHeight: '1.8' }}>
          <li><strong>macOS</strong>: <code>~/Library/Application Support/com.soundcapsule.app/config.json</code></li>
          <li><strong>Windows</strong>: <code>%APPDATA%\com.soundcapsule.app\config.json</code></li>
          <li><strong>Linux</strong>: <code>~/.config/com.soundcapsule.app/config.json</code></li>
        </ul>
        <p style={{ marginTop: '15px', fontSize: '14px', color: '#666' }}>
          💡 你可以用文本编辑器打开这个文件，直接查看和编辑配置！
        </p>
      </div>
    </div>
  );
}

export default ConfigTest;
