import React from 'react';
import { getApiUrl } from '../utils/apiClient';

/**
 * 调试面板 - 显示当前导出状态
 * 用于跟踪 REAPER 导出的文件名、预览音频、胶囊类型等关键信息
 */

export default function DebugStatePanel({
  currentCapsuleId,
  currentCapsule,
  previewAudio,
  currentCapsuleType,
  exportStatus
}) {
  return (
    <div style={{
      position: 'fixed',
      bottom: '20px',
      right: '20px',
      width: '400px',
      backgroundColor: 'rgba(0, 0, 0, 0.9)',
      border: '2px solid #ff0000',
      borderRadius: '8px',
      padding: '16px',
      fontFamily: 'monospace',
      fontSize: '12px',
      color: '#00ff00',
      zIndex: 9999,
      maxHeight: '80vh',
      overflow: 'auto'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '12px',
        paddingBottom: '8px',
        borderBottom: '1px solid #ff0000'
      }}>
        <h3 style={{ margin: 0, color: '#ff0000', fontSize: '16px' }}>
          🔍 调试面板 - 导出状态追踪
        </h3>
        <button
          onClick={() => window.location.reload()}
          style={{
            backgroundColor: '#ff0000',
            color: 'white',
            border: 'none',
            padding: '4px 8px',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '11px'
          }}
        >
          刷新页面
        </button>
      </div>

      <div style={{ spaceY: '8px' }}>
        {/* 当前胶囊 ID */}
        <div style={{ marginBottom: '12px' }}>
          <div style={{ color: '#ffff00', fontWeight: 'bold', marginBottom: '4px' }}>
            📦 当前胶囊 ID:
          </div>
          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
            padding: '8px',
            borderRadius: '4px',
            wordBreak: 'break-all'
          }}>
            {currentCapsuleId || (
              <span style={{ color: '#ff6666' }}>未设置</span>
            )}
          </div>
        </div>

        {/* 当前胶囊数据 */}
        <div style={{ marginBottom: '12px' }}>
          <div style={{ color: '#ffff00', fontWeight: 'bold', marginBottom: '4px' }}>
            📋 当前胶囊数据:
          </div>
          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
            padding: '8px',
            borderRadius: '4px',
            maxHeight: '150px',
            overflow: 'auto',
            fontSize: '11px'
          }}>
            {currentCapsule ? (
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                {JSON.stringify(currentCapsule, null, 2)}
              </pre>
            ) : (
              <span style={{ color: '#ff6666' }}>未设置</span>
            )}
          </div>
        </div>

        {/* 预览音频 URL */}
        <div style={{ marginBottom: '12px' }}>
          <div style={{ color: '#ffff00', fontWeight: 'bold', marginBottom: '4px' }}>
            🎵 预览音频 URL:
          </div>
          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
            padding: '8px',
            borderRadius: '4px',
            wordBreak: 'break-all',
            fontSize: '11px'
          }}>
            {currentCapsule?.preview_audio ? (
              <>
                <div>文件名: {currentCapsule.preview_audio}</div>
                <div style={{ marginTop: '4px', fontSize: '10px', color: '#aaa' }}>
                  完整URL: {currentCapsule?.preview_audio ? getApiUrl(`/api/capsules/${currentCapsuleId}/preview/${currentCapsule.preview_audio}`) : '-'}
                </div>
              </>
            ) : (
              <span style={{ color: '#ff6666' }}>未设置</span>
            )}
          </div>
        </div>

        {/* 胶囊类型 */}
        <div style={{ marginBottom: '12px' }}>
          <div style={{ color: '#ffff00', fontWeight: 'bold', marginBottom: '4px' }}>
            🏷️ 胶囊类型:
          </div>
          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
            padding: '8px',
            borderRadius: '4px'
          }}>
            {currentCapsule?.capsule_type || currentCapsuleType || (
              <span style={{ color: '#ff6666' }}>未设置</span>
            )}
          </div>
        </div>

        {/* 导出状态 */}
        <div style={{ marginBottom: '12px' }}>
          <div style={{ color: '#ffff00', fontWeight: 'bold', marginBottom: '4px' }}>
            ⚙️ 导出状态:
          </div>
          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
            padding: '8px',
            borderRadius: '4px'
          }}>
            {exportStatus || (
              <span style={{ color: '#ff6666' }}>未设置</span>
            )}
          </div>
        </div>

        {/* 预警信息 */}
        <div style={{
          marginTop: '16px',
          padding: '12px',
          backgroundColor: 'rgba(255, 0, 0, 0.2)',
          border: '1px solid #ff0000',
          borderRadius: '4px'
        }}>
          <div style={{ color: '#ff6666', fontWeight: 'bold', marginBottom: '8px' }}>
            ⚠️ 问题检查清单:
          </div>
          <div style={{ fontSize: '11px', lineHeight: '1.6' }}>
            <div style={{ marginBottom: '4px' }}>
              {currentCapsuleId ? '✅' : '❌'} 胶囊 ID 已设置
            </div>
            <div style={{ marginBottom: '4px' }}>
              {currentCapsule?.preview_audio ? '✅' : '❌'} 预览音频文件已设置
            </div>
            <div style={{ marginBottom: '4px' }}>
              {currentCapsule?.capsule_type ? '✅' : '❌'} 胶囊类型已设置
            </div>
            <div style={{ marginBottom: '4px' }}>
              {currentCapsule?.name ? '✅' : '❌'} 胶囊名称已设置
            </div>
          </div>
        </div>

        {/* 操作提示 */}
        <div style={{
          marginTop: '12px',
          padding: '8px',
          backgroundColor: 'rgba(0, 255, 0, 0.1)',
          border: '1px solid #00ff00',
          borderRadius: '4px',
          fontSize: '11px'
        }}>
          <div style={{ color: '#00ff00', fontWeight: 'bold', marginBottom: '4px' }}>
            💡 提示:
          </div>
          <div>
            如果看到 "未设置" 或显示的是旧数据，请点击 "刷新页面" 按钮。
            这意味着状态没有正确更新。
          </div>
        </div>
      </div>
    </div>
  );
}
