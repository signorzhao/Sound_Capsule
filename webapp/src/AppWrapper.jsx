/**
 * AppWrapper - 应用包装组件
 * 负责检查配置并决定显示初始化设置还是主应用
 */
import { useState, useEffect } from 'react';
import { getAppConfig } from './utils/configApi';
import InitialSetup from './components/InitialSetup';
import App from './App';

export default function AppWrapper() {
  const [showInitialSetup, setShowInitialSetup] = useState(false);
  const [isCheckingConfig, setIsCheckingConfig] = useState(true);
  const [config, setConfig] = useState(null);

  useEffect(() => {
    console.log('[AppWrapper] 组件已挂载，开始检查配置');
    checkConfig();
  }, []);

  const checkConfig = async () => {
    try {
      console.log('[AppWrapper] 正在读取配置...');
      const loadedConfig = await getAppConfig();
      console.log('[AppWrapper] 配置读取成功:', loadedConfig);
      setConfig(loadedConfig);

      // 检查必需的配置项
      const hasRequiredConfig = loadedConfig.reaper_path && loadedConfig.export_dir;
      console.log('[AppWrapper] 配置完整性检查:', { reaper_path: !!loadedConfig.reaper_path, export_dir: !!loadedConfig.export_dir, hasRequiredConfig });

      if (!hasRequiredConfig) {
        // 配置不完整，显示初始化设置
        console.log('[AppWrapper] 配置不完整，将显示初始化设置');
        setShowInitialSetup(true);
      } else {
        console.log('[AppWrapper] 配置完整，将显示主应用');
        setShowInitialSetup(false);
      }
    } catch (err) {
      console.error('[AppWrapper] 检查配置失败:', err);
      // 出错时也显示初始化设置
      setShowInitialSetup(true);
    } finally {
      setIsCheckingConfig(false);
    }
  };

  const handleSetupComplete = () => {
    console.log('[AppWrapper] 初始化设置完成，重新加载配置');
    // 重新检查配置
    checkConfig();
  };

  console.log('[AppWrapper] 渲染状态:', { isCheckingConfig, showInitialSetup });

  // 如果正在检查配置，显示加载界面
  if (isCheckingConfig) {
    console.log('[AppWrapper] 渲染加载界面');
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white',
        fontSize: '18px',
        fontWeight: 500
      }}>
        加载中...
      </div>
    );
  }

  // 如果需要显示初始化设置
  if (showInitialSetup) {
    console.log('[AppWrapper] 渲染初始化设置界面');
    return <InitialSetup onComplete={handleSetupComplete} />;
  }

  // 配置完整，显示主应用
  console.log('[AppWrapper] 渲染主应用界面');
  return <App />;
}
