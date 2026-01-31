import React, { useState, useCallback, useEffect } from 'react';
import { clsx } from 'clsx';
import {
  Save,
  Music,
  Tag,
  CheckCircle,
  XCircle,
  Loader2,
  AlertCircle,
  FileAudio,
  FolderOpen,
  X,
  Info
} from 'lucide-react';
import { getAppConfig } from '../utils/configApi';

// ==========================================
// 辅助组件
// ==========================================

const StepIndicator = ({ currentStep, totalSteps }) => {
  return (
    <div className="flex items-center justify-center gap-2 mb-8">
      {Array.from({ length: totalSteps }, (_, i) => (
        <React.Fragment key={i}>
          <div
            className={clsx(
              'w-3 h-3 rounded-full transition-all duration-300',
              i < currentStep
                ? 'bg-purple-500 scale-110'
                : i === currentStep - 1
                ? 'bg-purple-400 scale-125 ring-4 ring-purple-400/30'
                : 'bg-gray-700'
            )}
          />
          {i < totalSteps - 1 && (
            <div
              className={clsx(
                'w-8 h-0.5 transition-all duration-300',
                i < currentStep - 1 ? 'bg-purple-500' : 'bg-gray-700'
              )}
            />
          )}
        </React.Fragment>
      ))}
    </div>
  );
};

const FormField = ({ label, error, hint, required, children }) => {
  return (
    <div className="space-y-2">
      <label className="flex items-center gap-2 text-sm font-medium text-gray-300">
        {label}
        {required && <span className="text-red-400">*</span>}
      </label>
      {children}
      {hint && (
        <p className="text-xs text-gray-500 flex items-center gap-1">
          <Info size={12} />
          {hint}
        </p>
      )}
      {error && (
        <p className="text-xs text-red-400 flex items-center gap-1">
          <AlertCircle size={12} />
          {error}
        </p>
      )}
    </div>
  );
};

// ==========================================
// 步骤 1: 基本信息
// ==========================================

const BasicInfoStep = ({ data, onChange, errors, reaperTrigger }) => {
  return (
    <div className="space-y-6">
      {/* REAPER 触发提示 */}
      {reaperTrigger && (
        <div className="p-4 bg-green-900/20 rounded-lg border border-green-500/20 flex items-start gap-3">
          <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-gray-300">
            <p className="font-medium mb-1">检测到 REAPER 触发</p>
            <p className="text-gray-400">
              选中的 Items: <span className="text-green-400">{reaperTrigger.item_count}</span>
            </p>
          </div>
        </div>
      )}

      <FormField
        label="渲染预览音频"
        hint="渲染一段预览音频,便于在浏览器中播放"
      >
        <label className="flex items-center gap-3 cursor-pointer group">
          <div className="relative">
            <input
              type="checkbox"
              checked={data.renderPreview}
              onChange={(e) => onChange('renderPreview', e.target.checked)}
              className="sr-only"
            />
            <div
              className={clsx(
                'w-12 h-6 rounded-full transition-all duration-200',
                data.renderPreview
                  ? 'bg-purple-600'
                  : 'bg-gray-700 group-hover:bg-gray-600'
              )}
            >
              <div
                className={clsx(
                  'absolute top-1 w-4 h-4 bg-white rounded-full transition-all duration-200',
                  data.renderPreview ? 'left-7' : 'left-1'
                )}
              />
            </div>
          </div>
          <span className="text-sm text-gray-400">
            {data.renderPreview ? '已启用' : '已禁用'}
          </span>
        </label>
      </FormField>

      {/* 说明信息 */}
      <div className="p-4 bg-blue-900/20 rounded-lg border border-blue-500/20">
        <p className="text-sm text-gray-300">
          <span className="font-medium">导出说明：</span>
          点击"确认并开始导出"后，系统将自动在 REAPER 中导出选中的音频，
          并使用您选择的胶囊类型保存。
        </p>
      </div>
    </div>
  );
};

// ==========================================
// 步骤 2: REAPER 导出说明
// ==========================================

const ReaperExportStep = ({ data, onBack, onNext }) => {
  return (
    <div className="space-y-6">
      {/* 说明卡片 */}
      <div className="bg-gradient-to-br from-purple-900/20 to-indigo-900/20 rounded-xl p-6 border border-purple-500/20">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Music className="w-5 h-5 text-purple-400" />
          确认导出信息
        </h3>

        <div className="space-y-4">
          <div className="p-4 bg-gray-800/50 rounded-lg">
            <p className="text-sm text-gray-400 mb-2">胶囊名称</p>
            <p className="text-xl font-mono text-purple-400">
              {data.projectName}_{data.themeName}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 bg-gray-800/50 rounded-lg">
              <p className="text-sm text-gray-400 mb-1">渲染预览</p>
              <p className="text-lg text-white">
                {data.renderPreview ? '是' : '否'}
              </p>
            </div>
            <div className="p-4 bg-gray-800/50 rounded-lg">
              <p className="text-sm text-gray-400 mb-1">输出目录</p>
              <p className="text-sm text-white">
                {exportDir}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 提示信息 */}
      <div className="flex items-start gap-3 p-4 bg-blue-900/20 rounded-lg border border-blue-500/20">
        <Info className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-gray-300">
          <p className="font-medium mb-1">导出说明</p>
          <p className="mb-2">系统将自动执行以下操作:</p>
          <ul className="space-y-1 text-gray-400">
            <li>• 在 REAPER 中导出选中的音频 Item</li>
            <li>• 生成胶囊元数据和预览音频</li>
            <li>• 自动导入到数据库</li>
          </ul>
          <p className="mt-2 text-yellow-400">
            前提: 请确保已在 REAPER 中选中要导出的音频 Item
          </p>
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-700">
        <button
          onClick={onBack}
          className="text-sm text-gray-400 hover:text-white transition-colors"
        >
          ← 返回修改信息
        </button>

        <button
          onClick={onNext}
          className={clsx(
            'px-6 py-2.5 rounded-lg font-medium',
            'bg-gradient-to-r from-purple-600 to-indigo-600',
            'hover:from-purple-500 hover:to-indigo-500',
            'text-white',
            'shadow-lg shadow-purple-900/20',
            'transition-all duration-200',
            'hover:shadow-purple-900/40 hover:scale-105',
            'flex items-center gap-2'
          )}
        >
          <CheckCircle className="w-4 h-4" />
          <span>确认并开始导出</span>
        </button>
      </div>
    </div>
  );
};

const StepItem = ({ number, title, description, children }) => {
  return (
    <div className="flex gap-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-purple-600/20 border-2 border-purple-500 flex items-center justify-center">
        <span className="text-sm font-bold text-purple-400">{number}</span>
      </div>
      <div className="flex-1">
        <p className="text-white font-medium mb-1">{title}</p>
        <p className="text-sm text-gray-400 mb-2">{description}</p>
        {children}
      </div>
    </div>
  );
};

// ==========================================
// 步骤 3: 导入状态
// ==========================================

const ImportStatusStep = ({ data, status, error, onComplete, onStatusChange }) => {
  const [isExporting, setIsExporting] = useState(false);
  const [foundCapsule, setFoundCapsule] = useState(null);

  const handleAutoExport = useCallback(async () => {
    setIsExporting(true);

    // 通知父组件开始导出
    if (onStatusChange) {
      onStatusChange('scanning');
    }

    try {
      console.log('开始自动导出...');
      console.log('使用胶囊类型:', currentCapsuleType);
      console.log('渲染预览:', data.renderPreview);

      // 调用自动导出 API (使用 webui-export 端点)
      // 不再发送 project_name 和 theme_name，后端会使用 capsule_type 生成名称
      const exportResponse = await fetch('http://localhost:5002/api/capsules/webui-export', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          capsule_type: currentCapsuleType,
          render_preview: data.renderPreview,
          webui_port: 9000
        })
      });

      const exportResult = await exportResponse.json();

      if (!exportResult.success) {
        throw new Error(exportResult.error || '导出失败');
      }

      console.log('✅ REAPER 导出成功:', exportResult);
      console.log('========================================');
      console.log('📦 webui-export API 完整响应:');
      console.log(JSON.stringify(exportResult, null, 2));
      console.log('========================================');

      // webui-export API 已经在内部调用了 scan-and-import
      // 直接使用返回的 auto_imported 数据
      if (exportResult.auto_imported && exportResult.auto_imported.length > 0) {
        const importedCapsule = exportResult.auto_imported[0];
        console.log('🎉 导出并自动导入成功！');
        console.log('🆔 导入的胶囊 ID:', importedCapsule.id);
        console.log('📦 胶囊名称:', importedCapsule.name);
        console.log('🏷️  胶囊类型:', importedCapsule.capsule_type);

        // 更新状态
        setFoundCapsule(importedCapsule);
        if (onStatusChange) {
          onStatusChange('success');
        }

        // 通知父组件更新当前胶囊
        if (onSuccess) {
          onSuccess(importedCapsule);
        }
      } else {
        console.warn('⚠️ 导出成功但没有自动导入数据');
        console.log('📡 尝试从数据库获取最新的胶囊...');

        // 如果没有自动导入数据，从数据库获取最新的胶囊
        try {
          const capsulesResponse = await fetch('http://localhost:5002/api/capsules');
          const capsulesResult = await capsulesResponse.json();

          if (capsulesResult.success && capsulesResult.capsules && capsulesResult.capsules.length > 0) {
            const latestCapsule = capsulesResult.capsules[capsulesResult.capsules.length - 1];
            console.log('🆔 从数据库获取的最新胶囊 ID:', latestCapsule.id);
            console.log('📦 最新胶囊数据:', JSON.stringify(latestCapsule, null, 2));

            setFoundCapsule(latestCapsule);
            if (onStatusChange) {
              onStatusChange('success');
            }

            if (onSuccess) {
              onSuccess(latestCapsule);
            }
          } else {
            console.error('❌ 无法从数据库获取胶囊列表');
            if (onStatusChange) {
              onStatusChange('success');
            }
          }
        } catch (fetchError) {
          console.error('❌ 获取胶囊列表失败:', fetchError);
          if (onStatusChange) {
            onStatusChange('success');
          }
        }
      }
    } catch (err) {
      console.error('❌ 自动导出失败:', err);
      if (onStatusChange) {
        onStatusChange('error', err.message || '自动导出失败，请检查 REAPER 是否已打开并保存项目');
      }
    } finally {
      setIsExporting(false);
    }
  }, [data, onStatusChange, onSuccess]);

  return (
    <div className="space-y-6">
      {/* 状态显示 */}
      <div className="text-center py-8">
        {status === 'waiting' && (
          <div className="space-y-4">
            <div className="w-20 h-20 mx-auto rounded-full bg-gray-800 flex items-center justify-center">
              <Music className="w-10 h-10 text-gray-600" />
            </div>
            <div>
              <h3 className="text-xl font-semibold text-white mb-2">
                准备自动导出
              </h3>
              <p className="text-sm text-gray-400">
                点击下方按钮,系统将自动在 REAPER 中执行导出
              </p>
              <p className="text-xs text-gray-500 mt-2">
                前提: 请确保已在 REAPER 中选中要导出的音频 Item
              </p>
            </div>
          </div>
        )}

        {status === 'scanning' && (
          <div className="space-y-4">
            <div className="w-20 h-20 mx-auto rounded-full bg-purple-900/30 flex items-center justify-center">
              <Loader2 className="w-10 h-10 text-purple-400 animate-spin" />
            </div>
            <div>
              <h3 className="text-xl font-semibold text-white mb-2">
                正在自动导出...
              </h3>
              <p className="text-sm text-gray-400">
                REAPER 正在导出胶囊,请稍候
              </p>
            </div>
          </div>
        )}

        {status === 'success' && (
          <div className="space-y-4">
            <div className="w-20 h-20 mx-auto rounded-full bg-green-900/30 flex items-center justify-center">
              <CheckCircle className="w-10 h-10 text-green-400" />
            </div>
            <div>
              <h3 className="text-xl font-semibold text-white mb-2">
                导出成功!
              </h3>
              <p className="text-sm text-gray-400">
                胶囊已成功导出并导入数据库
              </p>
              {foundCapsule && (
                <div className="mt-4 p-4 bg-gray-800/50 rounded-lg">
                  <p className="text-sm text-gray-400">胶囊信息:</p>
                  <p className="text-lg font-mono text-purple-400 mt-1">{foundCapsule.name}</p>
                  <p className="text-xs text-gray-500 mt-2">ID: {foundCapsule.id}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {status === 'error' && (
          <div className="space-y-4">
            <div className="w-20 h-20 mx-auto rounded-full bg-red-900/30 flex items-center justify-center">
              <XCircle className="w-10 h-10 text-red-400" />
            </div>
            <div>
              <h3 className="text-xl font-semibold text-white mb-2">
                导出失败
              </h3>
              <p className="text-sm text-gray-400">
                {error || '未知错误'}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-3">
        {status === 'waiting' && (
          <>
            <button
              onClick={handleAutoExport}
              disabled={isExporting}
              className={clsx(
                'flex-1 px-6 py-3 rounded-lg font-medium',
                'bg-gradient-to-r from-purple-600 to-indigo-600',
                'hover:from-purple-500 hover:to-indigo-500',
                'text-white',
                'shadow-lg shadow-purple-900/20',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'transition-all duration-200'
              )}
            >
              {isExporting ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  导出中...
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  <Save className="w-5 h-5" />
                  一键导出
                </span>
              )}
            </button>
          </>
        )}

        {status === 'success' && (
          <button
            onClick={onComplete}
            className="flex-1 px-6 py-3 rounded-lg font-medium bg-green-600 hover:bg-green-500 text-white transition-all duration-200"
          >
            完成
          </button>
        )}

        {status === 'error' && (
          <>
            <button
              onClick={handleAutoExport}
              disabled={isExporting}
              className="flex-1 px-6 py-3 rounded-lg font-medium bg-purple-600 hover:bg-purple-500 text-white transition-all duration-200 disabled:opacity-50"
            >
              {isExporting ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  导出中...
                </span>
              ) : '重试'}
            </button>
          </>
        )}
      </div>
    </div>
  );
};

// ==========================================
// 主组件
// ==========================================

export default function CapsuleExportWizard({ onClose, onSuccess, currentCapsuleType, currentCapsuleId }) {
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState({
    projectName: '',
    themeName: '',
    renderPreview: true
  });
  const [errors, setErrors] = useState({});
  const [status, setStatus] = useState('waiting'); // waiting, scanning, success, error
  const [error, setError] = useState(null);
  const [reaperTrigger, setReaperTrigger] = useState(null);
  const [exportDir, setExportDir] = useState('data-pipeline/output/'); // 默认值

  const totalSteps = 3;

  // 加载用户配置
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await getAppConfig();
        if (config.export_dir) {
          setExportDir(config.export_dir + '/');
        }
      } catch (err) {
        console.error('加载配置失败:', err);
      }
    };
    loadConfig();
  }, []);

  // 检测 REAPER 触发
  useEffect(() => {
    const checkReaperTrigger = async () => {
      try {
        const response = await fetch('http://localhost:5002/api/capsules/check-reaper-trigger');
        const result = await response.json();

        if (result.has_trigger) {
          setReaperTrigger(result);
          setFormData(prev => ({
            ...prev,
            projectName: result.project_name || prev.projectName
          }));

          console.log('检测到 REAPER 触发:', result);
        }
      } catch (err) {
        console.error('检查 REAPER 触发失败:', err);
      }
    };

    checkReaperTrigger();
  }, []);

  // 验证步骤 1
  const validateStep1 = useCallback(() => {
    // 不需要验证任何字段，因为只有 renderPreview 开关
    return true;
  }, []);

  // 处理字段变化
  const handleFieldChange = useCallback((field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // 清除该字段的错误
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: null }));
    }
  }, [errors]);

  // 处理状态变化(从 ImportStatusStep 调用)
  const handleStatusChange = useCallback((newStatus, errorMsg) => {
    setStatus(newStatus);
    if (errorMsg) {
      setError(errorMsg);
    } else {
      setError(null);
    }
  }, []);

  // 下一步
  const handleNext = useCallback(() => {
    if (currentStep === 1) {
      if (validateStep1()) {
        setCurrentStep(2);
      }
    } else if (currentStep === 2) {
      setCurrentStep(3);
      setStatus('waiting');
      setError(null);
    }
  }, [currentStep, validateStep1]);

  // 上一步
  const handlePrevious = useCallback(() => {
    if (currentStep > 1) {
      setCurrentStep(prev => prev - 1);
    }
  }, [currentStep]);

  // 完成导出
  const handleComplete = useCallback(() => {
    if (onSuccess) {
      onSuccess(formData);
    }
    if (onClose) {
      onClose();
    }
  }, [formData, onSuccess, onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-2xl bg-gray-900 rounded-2xl shadow-2xl border border-gray-800">
        {/* 头部 */}
        <div className="flex items-center justify-between p-6 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-purple-600/20 flex items-center justify-center">
              <Save className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">导出胶囊</h2>
              <p className="text-sm text-gray-400">
                步骤 {currentStep} / {totalSteps}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-800 transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* 步骤指示器 */}
        <div className="px-6 pt-6">
          <StepIndicator currentStep={currentStep} totalSteps={totalSteps} />
        </div>

        {/* 内容 */}
        <div className="p-6">
          {currentStep === 1 && (
            <BasicInfoStep
              data={formData}
              onChange={handleFieldChange}
              errors={errors}
              reaperTrigger={reaperTrigger}
            />
          )}

          {currentStep === 2 && (
            <ReaperExportStep
              data={formData}
              onBack={handlePrevious}
              onNext={handleNext}
            />
          )}

          {currentStep === 3 && (
            <ImportStatusStep
              data={formData}
              status={status}
              error={error}
              onComplete={handleComplete}
              onStatusChange={handleStatusChange}
            />
          )}
        </div>

        {/* 底部按钮 */}
        {currentStep !== 2 && (
          <div className="flex items-center justify-between p-6 border-t border-gray-800">
            <button
              onClick={handlePrevious}
              disabled={currentStep === 1}
              className={clsx(
                'px-6 py-2.5 rounded-lg font-medium',
                'text-gray-400 hover:text-white',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'transition-all duration-200'
              )}
            >
              上一步
            </button>

            {currentStep < 3 && (
              <button
                onClick={handleNext}
                className="px-6 py-2.5 rounded-lg font-medium bg-purple-600 hover:bg-purple-500 text-white transition-all duration-200"
              >
                下一步
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// 导出子组件供外部使用
export { BasicInfoStep, ReaperExportStep, ImportStatusStep };
