import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import AppRouter from './AppRouter'
import AppWrapper from './AppWrapper'
import ConfigTest from './pages/ConfigTest'
import ToastProvider from './components/Toast'
import './index.css'

// 开发模式下显示配置测试页面
// 生产模式或需要使用主应用时，将此变量改为 false
const SHOW_CONFIG_TEST = false  // Phase D1 测试完成，恢复正常流程
const SKIP_CONFIG_CHECK = false  // 恢复正常配置检查流程
const ENABLE_AUTH = true  // Phase A: 启用认证系统

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ToastProvider>
      {SHOW_CONFIG_TEST ? (
        <ConfigTest />
      ) : ENABLE_AUTH ? (
        <BrowserRouter>
          <AppRouter />
        </BrowserRouter>
      ) : (
        SKIP_CONFIG_CHECK ? <AppWrapper /> : <AppWrapper />
      )}
    </ToastProvider>
  </React.StrictMode>,
)

