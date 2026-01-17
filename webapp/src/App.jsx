import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Layers, Zap, Maximize, Hash, Copy, Eraser, Sparkles, Check, CircleDot, Save, Package } from 'lucide-react';
import { clsx } from 'clsx';
import CapsuleExportWizard from './components/CapsuleExportWizard';
import SaveCapsuleHome from './components/SaveCapsuleHome';
import LensCompleteDialog from './components/LensCompleteDialog';
import CapsuleLibrary from './components/CapsuleLibrary';
import DebugStatePanel from './components/DebugStatePanel';
import UserMenu from './components/UserMenu';
import SyncIndicator from './components/SyncIndicator';
import InitialSetup from './components/InitialSetup';
import BootSync from './components/BootSync'; // Phase G2: 启动同步
import { useToast } from './components/Toast';
import { sendNotification, requestNotificationPermission } from './utils/tauriApi';
import { getAppConfig } from './utils/configApi';
import './components/SaveCapsuleHome.css';
import './components/CapsuleCard.css';
import './components/CapsuleTypeCard.css';

// ==========================================
// 默认透镜配置（用于备用）
// ==========================================

const DEFAULT_LENS_CONFIG = {
  texture: {
    id: 'texture',
    name: 'Texture / Timbre',
    nameCn: '质感',
    icon: 'Hash',
    color: 'from-purple-900/60 to-indigo-900/60',
    accentColor: '#8b5cf6',
    axis: {
      top: 'Playful / 趣味活跃',
      bottom: 'Serious / 写实严肃',
      left: 'Dark / 黑暗恐惧',
      right: 'Light / 光明治愈'
    }
  },
  source: {
    id: 'source',
    name: 'Source & Physics',
    nameCn: '源场',
    icon: 'Zap',
    color: 'from-orange-900/60 to-amber-900/60',
    accentColor: '#f59e0b',
    axis: {
      top: 'Sci-Fi / 科幻合成',
      bottom: 'Organic / 有机自然',
      left: 'Static / 静态铺底',
      right: 'Transient / 瞬态冲击'
    }
  },
  materiality: {
    id: 'materiality',
    name: 'Materiality / Room',
    nameCn: '材质',
    icon: 'Maximize',
    color: 'from-teal-900/60 to-cyan-900/60',
    accentColor: '#06b6d4',
    axis: {
      top: 'Warm / 暖软吸音',
      bottom: 'Cold / 冷硬反射',
      left: 'Close / 贴耳干涩',
      right: 'Distant / 遥远湿润'
    }
  }
};

// 图标映射
const ICON_MAP = {
  Hash, Zap, Maximize, CircleDot, Sparkles, Layers
};

// 颜色循环（用于新棱镜）
const COLOR_PALETTE = [
  { color: 'from-purple-900/60 to-indigo-900/60', accent: '#8b5cf6' },
  { color: 'from-orange-900/60 to-amber-900/60', accent: '#f59e0b' },
  { color: 'from-teal-900/60 to-cyan-900/60', accent: '#06b6d4' },
  { color: 'from-rose-900/60 to-pink-900/60', accent: '#ec4899' },
  { color: 'from-emerald-900/60 to-green-900/60', accent: '#10b981' },
  { color: 'from-blue-900/60 to-sky-900/60', accent: '#3b82f6' },
];

// ==========================================
// KNN 工具函数
// ==========================================

function euclideanDistance(x1, y1, x2, y2) {
  const dx = x1 - x2;
  const dy = y1 - y2;
  return Math.sqrt(dx * dx + dy * dy);
}

function findNearestKNN(points, cursorX, cursorY, k = 12) {
  if (!points || points.length === 0) return [];

  const withDistance = points.map(point => ({
    ...point,
    distance: euclideanDistance(cursorX, cursorY, point.x, point.y)
  }));

  withDistance.sort((a, b) => a.distance - b.distance);

  return withDistance.slice(0, k);
}

// ==========================================
// 主应用组件
// ==========================================

export default function App() {
  const toast = useToast();

  // 状态
  const [activeLens, setActiveLens] = useState('texture');
  const [cursorPos, setCursorPos] = useState({ x: 50, y: 50 });
  const [selectedTags, setSelectedTags] = useState([]);
  const [vectorData, setVectorData] = useState(null);
  const [lensConfig, setLensConfig] = useState(DEFAULT_LENS_CONFIG);
  const [isLoading, setIsLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [isDragging, setIsDragging] = useState(false); // 拖拽状态
  const [selectionRadius, setSelectionRadius] = useState(15); // 手动调节选取半径 (0-100)
  const [showExportWizard, setShowExportWizard] = useState(false); // 导出向导显示状态

  // Phase 5 新增状态
  const [currentView, setCurrentView] = useState('save-home'); // 'save-home' | 'lens' | 'library'
  const [saveProgress, setSaveProgress] = useState(0);
  const [saveStatus, setSaveStatus] = useState('idle'); // 'idle' | 'saving' | 'success'
  const [currentCapsuleId, setCurrentCapsuleId] = useState(null);
  const [currentCapsule, setCurrentCapsule] = useState(null); // Phase 5.3: 存储完整胶囊数据
  const [completedLenses, setCompletedLenses] = useState([]);
  const [allSelectedTags, setAllSelectedTags] = useState({}); // 动态初始化为空对象
  const [lensCursorPosition, setLensCursorPosition] = useState({}); // 动态初始化为空对象

  // Phase 5.5: 胶囊库和编辑功能
  const [capsuleList, setCapsuleList] = useState([]);
  const [isEditMode, setIsEditMode] = useState(false); // 标记是否是编辑模式
  const [libraryRefreshTrigger, setLibraryRefreshTrigger] = useState(0); // 用于刷新胶囊库缓存

  // Phase 5.3: 音频辅助选词
  const [previewAudio, setPreviewAudio] = useState(null);
  const previewAudioRef = useRef(null);
  const dragStartedInsideRef = useRef(false); // 标记拖拽是否在棱镜内部开始

  // Phase 5.4: 多棱镜管理
  const [showCompleteDialog, setShowCompleteDialog] = useState(false);
  const [isContinueMode, setIsContinueMode] = useState(false); // 标记是否是继续模式

  // Phase F: 用户配置
  const [userConfig, setUserConfig] = useState(null);
  const [showInitialSetup, setShowInitialSetup] = useState(false);

  // Phase G2: 启动同步状态
  const [showBootSync, setShowBootSync] = useState(false);
  const [isBootSyncComplete, setIsBootSyncComplete] = useState(false);

  // Phase G2: 启动同步回调（使用 useCallback 避免重复创建）
  const handleBootSyncComplete = useCallback((result) => {
    console.log('✅ [BootSync] 启动同步完成:', result);
    setShowBootSync(false);
    setIsBootSyncComplete(true);
  }, []);

  const handleBootSyncError = useCallback((error) => {
    console.error('❌ [BootSync] 启动同步失败:', error);
    // 即使失败也允许进入主界面（用户可以手动同步）
    setShowBootSync(false);
    setIsBootSyncComplete(true);
  }, []);

  const containerRef = useRef(null);

  const currentLens = lensConfig[activeLens] || Object.values(lensConfig)[0];

  // ==========================================
  // 加载向量数据
  // ==========================================

  useEffect(() => {
    async function loadData() {
      try {
        // 请求通知权限
        await requestNotificationPermission();

        // 1. 从 API 加载棱镜和力场数据 (不再使用本地静态 JSON)
        console.log('📡 正在从 API 加载棱镜力场数据...');
        const response = await fetch('http://localhost:5002/api/prisms/field');
        if (!response.ok) {
          throw new Error('API 无法提供力场数据');
        }

        const data = await response.json();
        console.log('✅ 加载的棱镜:', Object.keys(data), '共', Object.keys(data).length, '个');
        
        // 检查是否是错误响应
        if (data.success === false) {
          throw new Error(data.error || 'API 返回错误');
        }
        
        // 检查是否返回了空对象
        if (Object.keys(data).length === 0) {
          throw new Error('API 返回空数据');
        }
        
        setVectorData(data);

        // 动态生成棱镜配置
        const dynamicConfig = {};
        let colorIndex = 0;

        Object.keys(data).forEach(key => {
          const lensData = data[key];

          // 如果有默认配置就使用，否则动态生成
          if (DEFAULT_LENS_CONFIG[key]) {
            dynamicConfig[key] = { ...DEFAULT_LENS_CONFIG[key] };
          } else {
            // 动态生成新棱镜配置
            const colorSet = COLOR_PALETTE[colorIndex % COLOR_PALETTE.length];
            colorIndex++;

            // 解析名称
            const name = lensData.name || key;
            const nameParts = name.split('/');
            const nameCn = nameParts[1]?.trim().split(' ')[0] || key;

            dynamicConfig[key] = {
              id: key,
              name: nameParts[0]?.trim() || key,
              nameCn: nameCn,
              icon: 'CircleDot',
              color: colorSet.color,
              accentColor: colorSet.accent,
              axis: {
                top: lensData.axes?.y_label?.pos || 'Y+',
                bottom: lensData.axes?.y_label?.neg || 'Y-',
                left: lensData.axes?.x_label?.neg || 'X-',
                right: lensData.axes?.x_label?.pos || 'X+'
              }
            };
          }
        });

        setLensConfig(dynamicConfig);

        // 初始化 allSelectedTags 和 lensCursorPosition
        const initialTags = {};
        const initialPositions = {};
        Object.keys(dynamicConfig).forEach(lensId => {
          initialTags[lensId] = [];
          initialPositions[lensId] = { x: 50, y: 50 };
        });
        setAllSelectedTags(initialTags);
        setLensCursorPosition(initialPositions);

        // 如果当前选中的棱镜不存在，切换到第一个
        if (!dynamicConfig[activeLens]) {
          setActiveLens(Object.keys(dynamicConfig)[0]);
        }

        setIsLoading(false);
      } catch (error) {
        console.error('加载向量数据失败:', error);
        // 使用演示数据和默认配置
        setVectorData(generateDemoData());
        
        // 确保 lensConfig 使用默认配置
        console.log('⚠️ 使用默认棱镜配置 DEFAULT_LENS_CONFIG');
        setLensConfig(DEFAULT_LENS_CONFIG);
        
        // 初始化 allSelectedTags 和 lensCursorPosition
        const initialTags = {};
        const initialPositions = {};
        Object.keys(DEFAULT_LENS_CONFIG).forEach(lensId => {
          initialTags[lensId] = [];
          initialPositions[lensId] = { x: 50, y: 50 };
        });
        setAllSelectedTags(initialTags);
        setLensCursorPosition(initialPositions);
        
        setIsLoading(false);
      }
    }
    loadData();
  }, []);

  // ==========================================
  // Phase F: 加载用户配置
  // ==========================================

  useEffect(() => {
    console.log('[App] 配置加载 useEffect 触发', Date.now());
    
    async function loadConfig() {
      try {
        console.log('📋 加载用户配置...');
        const config = await getAppConfig();
        console.log('✅ 用户配置加载成功:', config);

        // 检查配置是否完整（至少需要 export_dir）
        if (!config || !config.export_dir) {
          console.log('⚠️  配置不完整，显示初始化设置界面');
          setShowInitialSetup(true);
        } else {
          console.log('✅ 配置完整');
          setShowInitialSetup(false);

          // Phase G2: 配置完整后，检查是否需要启动同步
          const accessToken = localStorage.getItem('access_token');
          if (accessToken && !isBootSyncComplete) {
            console.log('🚀 [BootSync] 用户已登录，触发启动同步');
            setShowBootSync(true);
          } else {
            console.log('ℹ️ [BootSync] 跳过启动同步（无 token 或已完成）');
            setIsBootSyncComplete(true);
          }
        }

        setUserConfig(config);
      } catch (error) {
        console.error('❌ 加载用户配置失败:', error);
        // 加载失败也显示初始化界面
        setShowInitialSetup(true);
      }
    }
    loadConfig();
  }, []); // ✅ 空依赖数组，只在挂载时执行一次

  // ==========================================
  // 监听配置更新事件
  // ==========================================

  useEffect(() => {
    const handleConfigUpdate = (event) => {
      console.log('📢 收到配置更新事件:', event.detail);
      setUserConfig(event.detail);
    };

    window.addEventListener('config-updated', handleConfigUpdate);

    return () => {
      window.removeEventListener('config-updated', handleConfigUpdate);
    };
  }, []);

  // ==========================================
  // Phase 5.4: 棱镜切换时加载已保存的标签
  // ==========================================

  useEffect(() => {
    // 如果是继续模式（刚点击了"继续选择"），不加载旧标签
    if (isContinueMode) {
      setIsContinueMode(false);
      setSelectedTags([]);
      return;
    }

    // 如果切换到的棱镜已经有保存的标签，自动加载
    if (allSelectedTags[activeLens] && allSelectedTags[activeLens].length > 0) {
      // 统一字段名，确保与 Suggested Tags 兼容
      const normalizedTags = allSelectedTags[activeLens].map((tag, index) => {
        // 处理空字符串的word_id
        const wordId = tag.word_id && tag.word_id !== '' ? tag.word_id : null;
        const tagId = tag.id && tag.id !== '' ? tag.id : null;
        const word = tag.word && tag.word !== '' ? tag.word : null;
        const wordCn = tag.word_cn || tag.zh;
        const wordEn = tag.word_en || tag.en;

        // 创建一个稳定的唯一标识符
        let uniqueId;
        if (wordId) {
          uniqueId = wordId;
        } else if (tagId) {
          uniqueId = tagId;
        } else if (word) {
          uniqueId = word;
        } else {
          // 最后的回退：使用中英文组合 + 索引
          uniqueId = `${wordCn}-${wordEn}-${index}`;
        }

        return {
          id: uniqueId,
          word_id: wordId || uniqueId,
          word: word || uniqueId,
          zh: wordCn,
          en: wordEn,
          word_cn: wordCn,
          word_en: wordEn,
          x: tag.x,
          y: tag.y
        };
      });
      setSelectedTags(normalizedTags);
      console.log(`加载 ${activeLens} 棱镜的已选标签:`, normalizedTags.length, normalizedTags);
    } else {
      // 如果没有保存的标签，清空当前选择
      setSelectedTags([]);
    }
  }, [activeLens, isContinueMode, allSelectedTags]); // 🔥 添加 allSelectedTags 依赖

  // ==========================================
  // 生成演示数据 (开发阶段使用)
  // ==========================================

  function generateDemoData() {
    const demoWords = [
      // 质感词汇
      { word: 'Gritty', zh: '粗粝', x: 15, y: 20 },
      { word: 'Silky', zh: '丝滑', x: 85, y: 25 },
      { word: 'Rusty', zh: '生锈', x: 10, y: 30 },
      { word: 'Crystalline', zh: '水晶', x: 90, y: 15 },
      { word: 'Heavy', zh: '沉重', x: 20, y: 35 },
      { word: 'Airy', zh: '通透', x: 80, y: 20 },
      { word: 'Slimy', zh: '粘稠', x: 25, y: 75 },
      { word: 'Bouncy', zh: '弹跳', x: 75, y: 80 },
      { word: 'Glitchy', zh: '故障', x: 30, y: 70 },
      { word: 'Magical', zh: '魔法', x: 85, y: 85 },
      { word: 'Industrial', zh: '工业', x: 15, y: 25 },
      { word: 'Organic', zh: '有机', x: 80, y: 30 },
      { word: 'Acidic', zh: '酸性', x: 20, y: 80 },
      { word: 'Shimmering', zh: '闪烁', x: 90, y: 75 },
      { word: 'Muddy', zh: '浑浊', x: 25, y: 65 },
      { word: 'Snappy', zh: '清脆', x: 85, y: 70 },
      { word: 'Piercing', zh: '刺骨', x: 10, y: 15 },
      { word: 'Woody', zh: '木质', x: 75, y: 35 },
      { word: 'Twisted', zh: '扭曲', x: 35, y: 75 },
      { word: 'Uplifting', zh: '激昂', x: 80, y: 90 },
      { word: 'Dark', zh: '黑暗', x: 12, y: 40 },
      { word: 'Bright', zh: '明亮', x: 88, y: 45 },
      { word: 'Warm', zh: '温暖', x: 70, y: 40 },
      { word: 'Cold', zh: '冷冽', x: 25, y: 50 },
      { word: 'Smooth', zh: '光滑', x: 78, y: 55 },
      { word: 'Rough', zh: '粗糙', x: 22, y: 45 },
      { word: 'Metallic', zh: '金属', x: 30, y: 20 },
      { word: 'Plastic', zh: '塑料', x: 65, y: 65 },
      { word: 'Ethereal', zh: '空灵', x: 82, y: 15 },
      { word: 'Gloomy', zh: '阴郁', x: 18, y: 55 },
      { word: 'Punchy', zh: '有冲劲', x: 45, y: 25 },
      { word: 'Fluffy', zh: '蓬松', x: 72, y: 85 },
      { word: 'Crisp', zh: '酥脆', x: 85, y: 50 },
      { word: 'Muffled', zh: '闷响', x: 35, y: 60 },
      { word: 'Resonant', zh: '共鸣', x: 55, y: 30 },
      { word: 'Hollow', zh: '空心', x: 40, y: 50 },
      { word: 'Dense', zh: '密集', x: 30, y: 35 },
      { word: 'Sparse', zh: '稀疏', x: 70, y: 60 },
      { word: 'Vintage', zh: '复古', x: 45, y: 40 },
      { word: 'Modern', zh: '现代', x: 60, y: 45 },
    ];

    return {
      texture: {
        name: 'Texture / Timbre (质感)',
        points: demoWords
      },
      source: {
        name: 'Source & Physics (源场)',
        points: demoWords.map(w => ({
          ...w,
          x: (w.x + 15) % 100,
          y: (w.y + 20) % 100
        }))
      },
      materiality: {
        name: 'Materiality / Room (材质)',
        points: demoWords.map(w => ({
          ...w,
          x: (w.x + 30) % 100,
          y: (w.y + 10) % 100
        }))
      }
    };
  }

  // ==========================================
  // 计算推荐词汇 (KNN)
  // ==========================================

  const suggestedWords = useMemo(() => {
    if (!vectorData || !vectorData[activeLens]) return [];

    const points = vectorData[activeLens].points;
    // 首先找出最近的词，然后过滤掉超出半径的
    const nearest = findNearestKNN(points, cursorPos.x, cursorPos.y, 20);
    return nearest.filter(p => p.distance <= selectionRadius);
  }, [vectorData, activeLens, cursorPos, selectionRadius]);

  // ==========================================
  // Phase 5: 保存胶囊处理
  // ==========================================

  const handleSaveCapsule = async (data) => {
    console.log('========================================');
    console.log('🚀 开始保存胶囊');
    console.log('========================================');
    console.log('📦 接收到的数据:', JSON.stringify(data, null, 2));

    // 检查配置是否存在
    if (!userConfig || !userConfig.export_dir) {
      const error = '导出目录未配置，请先在设置中配置导出目录';
      console.error('❌', error);
      console.error('📋 当前配置:', userConfig);
      toast.error(error);
      setSaveStatus('idle');
      return;
    }

    console.log('📁 使用导出目录:', userConfig.export_dir);

    // 构造正确的请求数据
    const requestData = {
      capsule_type: data.capsule_type,
      render_preview: data.render_preview ?? true,
      webui_port: data.webui_port ?? 9000,
      export_dir: userConfig.export_dir  // 添加导出目录
    };

    console.log('📦 发送到 API 的数据:', JSON.stringify(requestData, null, 2));
    console.log('📦 胶囊类型:', requestData.capsule_type);

    setSaveStatus('saving');
    setSaveProgress(0);

    // 模拟进度
    const interval = setInterval(() => {
      setSaveProgress(prev => prev >= 90 ? 90 : prev + 10);
    }, 200);

    try {
      console.log('📡 发送导出请求到 API...');
      const response = await fetch('http://localhost:5002/api/capsules/webui-export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
      });

      const result = await response.json();
      console.log('📡 API 响应:', JSON.stringify(result, null, 2));

      clearInterval(interval);
      setSaveProgress(100);

      if (result.success) {
        console.log('✅ 导出成功！');
        console.log('🆔 新胶囊 ID:', result.capsule_id);
        console.log('📁 胶囊名称:', result.capsule_name);

        setSaveStatus('success');
        setCurrentCapsuleId(result.capsule_id);

        // 触发数据变更事件，通知 SyncContext 更新同步状态
        window.dispatchEvent(new Event('dataChanged'));
        console.log('🔄 已触发 dataChanged 事件，同步状态将自动更新');

        // 发送桌面通知
        await sendNotification({
          title: '胶囊保存成功',
          body: `已成功创建 ${data.capsule_type} 胶囊`
        });

        // 从 API 获取完整的胶囊数据（包含 preview_audio 等字段）
        console.log('📡 获取完整胶囊数据...');
        try {
          const capsuleResponse = await fetch(`http://localhost:5002/api/capsules/${result.capsule_id}`);
          const responseData = await capsuleResponse.json();
          const capsuleData = responseData.capsule; // 从响应中提取 capsule 对象
          console.log('✅ 完整胶囊数据:', JSON.stringify(capsuleData, null, 2));
          console.log('🎵 预览音频文件:', capsuleData.preview_audio);
          console.log('🏷️  保存的胶囊类型:', capsuleData.capsule_type);
          setCurrentCapsule(capsuleData);
        } catch (error) {
          console.error('❌ 获取完整胶囊数据失败:', error);
        }

        // 延迟跳转到对应棱镜
        setTimeout(() => {
          const lensMap = {
            'magic': 'texture',
            'impact': 'temperament',
            'atmosphere': 'materiality'
          };

          const targetLens = lensMap[data.capsule_type] || 'texture';
          console.log('🎯 跳转到棱镜:', targetLens);
          console.log('========================================');

          setActiveLens(targetLens);
          setCurrentView('lens');

          // 重置保存状态
          setTimeout(() => {
            setSaveStatus('idle');
            setSaveProgress(0);
          }, 500);
        }, 1000);
      } else {
        throw new Error(result.error || '保存失败');
      }
    } catch (error) {
      console.error('保存失败:', error);
      setSaveStatus('idle');
      setSaveProgress(0);
      toast.error('保存失败: ' + error.message);
    }
  };

  // ==========================================
  // Phase 5.5: 胶囊库管理
  // ==========================================

  // 加载胶囊列表
  const loadCapsules = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:5002/api/capsules?limit=100');
      const data = await response.json();

      if (data.success) {
        setCapsuleList(data.capsules);
        console.log('加载胶囊列表:', data.capsules.length, '个');
      }
    } catch (error) {
      console.error('加载胶囊列表失败:', error);
    }
  }, []);

  // 当切换到胶囊库视图时加载列表
  useEffect(() => {
    if (currentView === 'library') {
      loadCapsules();
    }
  }, [currentView, loadCapsules]);

  // 编辑胶囊 - 进入棱镜界面
  const handleEditCapsule = async (capsule) => {
    try {
      console.log('编辑胶囊:', capsule);
      console.log('当前 lensConfig:', lensConfig, '棱镜数量:', Object.keys(lensConfig).length);

      // 检查 lensConfig 是否有效
      if (!lensConfig || Object.keys(lensConfig).length === 0) {
        console.error('lensConfig 为空，无法编辑胶囊');
        toast.error('棱镜配置未加载，请刷新页面后重试');
        return;
      }

      // 获取胶囊的标签数据
      const response = await fetch(`http://localhost:5002/api/capsules/${capsule.id}/tags`);
      const data = await response.json();
      console.log('获取标签响应:', data);

      if (!data.success) {
        console.error('获取标签失败:', data.error || data.message);
        toast.error('获取标签失败: ' + (data.error || data.message || '未知错误'));
        return;
      }

      if (data.success) {
        const { tags, capsule: capsuleData } = data;

        // 设置胶囊ID和数据
        setCurrentCapsuleId(capsule.id);
        setCurrentCapsule(capsuleData);
        setIsEditMode(true);

        // 标准化标签数据并加载到 allSelectedTags
        const normalizedTags = {};
        // 动态遍历所有棱镜，而不是硬编码4个
        Object.keys(lensConfig).forEach(lens => {
          normalizedTags[lens] = (tags[lens] || []).map((tag, index) => {
            // 处理空字符串的word_id
            const wordId = tag.word_id && tag.word_id !== '' ? tag.word_id : null;
            const tagId = tag.id && tag.id !== '' ? tag.id : null;
            const word = tag.word && tag.word !== '' ? tag.word : null;
            const wordCn = tag.word_cn || tag.zh;
            const wordEn = tag.word_en || tag.en;

            // 创建一个稳定的唯一标识符
            let uniqueId;
            if (wordId) {
              uniqueId = wordId;
            } else if (tagId) {
              uniqueId = tagId;
            } else if (word) {
              uniqueId = word;
            } else {
              // 最后的回退：使用中英文组合 + 索引
              uniqueId = `${wordCn}-${wordEn}-${index}`;
            }

            return {
              id: uniqueId,
              word_id: wordId || uniqueId,
              word: word || uniqueId,
              zh: wordCn,
              en: wordEn,
              word_cn: wordCn,
              word_en: wordEn,
              x: tag.x,
              y: tag.y
            };
          });
        });

        setAllSelectedTags(normalizedTags);

        // 标记已完成的棱镜
        const completed = Object.keys(tags).filter(lens => tags[lens] && tags[lens].length > 0);
        setCompletedLenses(completed);

        // 跳转到第一个有标签的棱镜，或默认到 texture
        const firstLens = completed.length > 0 ? completed[0] : 'texture';
        setActiveLens(firstLens);
        setCurrentView('lens');

        console.log('加载胶囊标签完成:', normalizedTags);
      }
    } catch (error) {
      console.error('加载胶囊标签失败:', error);
      toast.error('加载胶囊失败: ' + error.message);
    }
  };

  // 删除胶囊
  const handleDeleteCapsule = async (capsule) => {
    if (!confirm(`确定要删除胶囊 "${capsule.name}" 吗？\n\n注意：此操作只删除数据库记录，不会删除服务器上的胶囊文件。`)) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:5002/api/capsules/${capsule.id}`, {
        method: 'DELETE'
      });

      const data = await response.json();

      if (data.success) {
        console.log('删除胶囊成功:', data);
        toast.success('删除成功');
        // 重新加载列表
        loadCapsules();
      } else {
        throw new Error(data.error || '删除失败');
      }
    } catch (error) {
      console.error('删除胶囊失败:', error);
      toast.error('删除失败: ' + error.message);
    }
  };

  // 返回主页
  const handleBackToHome = () => {
    setCurrentView('save-home');
    setIsEditMode(false);
    setCurrentCapsuleId(null);
    setCurrentCapsule(null);
    setSelectedTags([]);
    setAllSelectedTags({
      texture: [],
      source: [],
      materiality: [],
      temperament: []
    });
    setCompletedLenses([]);
  };

  // Phase 5.3: 播放预览音频
  const playPreviewAudio = useCallback(() => {
    // 停止并清理之前的音频
    if (previewAudioRef.current) {
      previewAudioRef.current.pause();
      previewAudioRef.current.currentTime = 0;
      previewAudioRef.current.src = '';  // 清除源，释放资源
      previewAudioRef.current.load();    // 强制重新加载
      previewAudioRef.current = null;
    }

    // 只有在有胶囊数据时才播放
    if (!currentCapsule || !currentCapsule.preview_audio) {
      console.log('没有胶囊数据或预览音频');
      console.log('currentCapsule:', currentCapsule);
      console.log('currentCapsuleId:', currentCapsuleId);
      return;
    }

    try {
      // 使用实际的文件名，添加时间戳防止浏览器缓存
      const timestamp = Date.now();
      const audioUrl = `http://localhost:5002/api/capsules/${currentCapsuleId}/preview/${currentCapsule.preview_audio}?t=${timestamp}`;
      console.log('播放音频:', audioUrl);
      console.log('胶囊ID:', currentCapsuleId);
      console.log('预览文件:', currentCapsule.preview_audio);

      const audio = new Audio(audioUrl);
      audio.play().catch(err => {
        console.log('音频播放失败:', err);
      });

      setPreviewAudio(audio);
      previewAudioRef.current = audio;
    } catch (error) {
      console.error('创建音频失败:', error);
    }
  }, [currentCapsule, currentCapsuleId]);

  // 清理音频
  useEffect(() => {
    return () => {
      if (previewAudioRef.current) {
        previewAudioRef.current.pause();
        previewAudioRef.current = null;
      }
    };
  }, []);

  // ==========================================
  // 交互处理
  // ==========================================

  // 计算并设置光标位置
  const updateCursorPosition = useCallback((e) => {
    if (!containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;

    let x = ((clientX - rect.left) / rect.width) * 100;
    let y = ((clientY - rect.top) / rect.height) * 100;

    x = Math.max(0, Math.min(100, x));
    y = Math.max(0, Math.min(100, y));

    setCursorPos({ x, y });
  }, []);

  // 开始拖拽
  const handleDragStart = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
    dragStartedInsideRef.current = true; // 标记拖拽在棱镜内部开始
    updateCursorPosition(e);
  }, [updateCursorPosition]);

  // 拖拽移动
  const handleDragMove = useCallback((e) => {
    if (!isDragging) return;
    updateCursorPosition(e);
  }, [isDragging, updateCursorPosition]);

  // 结束拖拽（只在棱镜内部点击时播放音频）
  const handleDragEnd = useCallback(() => {
    // 只在拖拽是从棱镜内部开始的情况下播放音频
    if (dragStartedInsideRef.current && currentCapsuleId) {
      playPreviewAudio();
    }

    setIsDragging(false);
    dragStartedInsideRef.current = false; // 重置标记
  }, [currentCapsuleId, playPreviewAudio]);

  const toggleTag = useCallback((item) => {
    setSelectedTags(prev => {
      // 使用多重匹配条件来精确定位标签
      const matchIndex = prev.findIndex((t) => {
        // 优先使用唯一标识符匹配
        const itemKey = item.word_id || item.id || item.word;
        const tagKey = t.word_id || t.id || t.word;

        // 如果有唯一标识符，使用标识符匹配
        if (itemKey && tagKey) {
          return itemKey === tagKey;
        }

        // 如果没有唯一标识符，使用多个字段组合匹配
        const itemCn = item.word_cn || item.zh;
        const tagCn = t.word_cn || t.zh;
        const itemEn = item.word_en || item.en;
        const tagEn = t.word_en || t.en;

        // 中文、英文都必须匹配
        return itemCn === tagCn && itemEn === tagEn;
      });

      if (matchIndex !== -1) {
        // 找到匹配项，移除它
        console.log(`删除标签:`, prev[matchIndex], `索引: ${matchIndex}`);
        return prev.filter((_, idx) => idx !== matchIndex);
      } else {
        // 没找到，添加新标签
        console.log(`添加标签:`, item);
        return [...prev, item];
      }
    });
  }, []);

  const copyTags = useCallback(() => {
    const text = selectedTags
      .map(t => typeof t === 'object' ? t.zh : t)
      .join(' ');

    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [selectedTags]);

  const clearTags = useCallback(() => {
    setSelectedTags([]);
  }, []);

  // Phase 5.4: 完成当前棱镜
  const handleLensComplete = useCallback(() => {
    // 🔥 修复：无论有没有标签，都保存当前状态到 allSelectedTags
    // 这样清除标签（空数组）也能正确保存
    setAllSelectedTags(prev => ({
      ...prev,
      [activeLens]: selectedTags
    }));
    console.log(`保存 ${activeLens} 棱镜的标签:`, selectedTags.length, '个');

    // 添加到已完成列表
    setCompletedLenses(prev => [...prev, activeLens]);

    // 显示对话框
    setShowCompleteDialog(true);
  }, [activeLens, selectedTags]);

  // Phase 5.4: 继续选择其他棱镜
  const handleContinueSelection = useCallback(() => {
    setShowCompleteDialog(false);

    // 找到下一个未完成的棱镜（动态从 lensConfig 获取）
    const allLenses = Object.keys(lensConfig);
    const nextLens = allLenses.find(lens => !completedLenses.includes(lens) && lens !== activeLens);

    if (nextLens) {
      setIsContinueMode(true); // 设置继续模式标记
      setActiveLens(nextLens);
    }
  }, [completedLenses, activeLens]);

  // Phase 5.4: 完成所有标签并保存
  const handleFinishAllTags = useCallback(async () => {
    setShowCompleteDialog(false);

    if (!currentCapsuleId) {
      toast.error('没有胶囊ID，无法保存标签');
      return;
    }

    // 收集所有标签
    const allTags = {
      ...allSelectedTags,
      [activeLens]: selectedTags  // 包含当前棱镜的标签
    };

    console.log('准备保存的所有标签:', allTags);

    try {
      // 编辑模式使用 PUT（覆盖），新建模式使用 POST
      const method = isEditMode ? 'PUT' : 'POST';

      // 调用 API 保存标签
      const response = await fetch(`http://localhost:5002/api/capsules/${currentCapsuleId}/tags`, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(allTags)
      });

      const result = await response.json();

      if (result.success) {
        toast.success(`${isEditMode ? '更新' : '保存'}成功！`);

        // 触发胶囊库刷新（清除 tags 缓存）
        setLibraryRefreshTrigger(prev => prev + 1);

        // 跳转到胶囊库视图
        setCurrentView('library');
        setIsEditMode(false); // 退出编辑模式

        // 清理状态
        setSelectedTags([]);
        setAllSelectedTags({
          texture: [],
          source: [],
          materiality: [],
          temperament: []
        });
        setCompletedLenses([]);
        setCurrentCapsuleId(null);
        setCurrentCapsule(null);
      } else {
        toast.error('保存失败: ' + (result.error || '未知错误'));
      }
    } catch (error) {
      console.error('保存标签失败:', error);
      toast.error('保存失败: ' + error.message);
    }
  }, [currentCapsuleId, allSelectedTags, activeLens, selectedTags, isEditMode]);

  // ==========================================
  // 渲染
  // ==========================================

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Sparkles className="w-12 h-12 text-purple-500 animate-pulse mx-auto mb-4" />
          <p className="text-gray-400">加载语义向量数据...</p>
        </div>
      </div>
    );
  }

  // 显示初始化设置界面（如果配置不完整）- 优先级最高
  if (showInitialSetup) {
    return (
      <InitialSetup
        onComplete={() => {
          console.log('✅ 初始化设置完成，重新加载配置');
          setShowInitialSetup(false);
          
          // 重新加载配置
          getAppConfig().then(config => {
            setUserConfig(config);
            
            // 初始化完成后，检查是否需要触发 BootSync
            const accessToken = localStorage.getItem('access_token');
            if (accessToken && !isBootSyncComplete) {
              console.log('🚀 [BootSync] 初始化完成，触发启动同步');
              setShowBootSync(true);
            } else {
              console.log('ℹ️ [BootSync] 跳过启动同步（无 token 或已完成）');
              setIsBootSyncComplete(true);
            }
          });
        }}
      />
    );
  }

  // Phase G2: 显示启动同步界面（优先级第二，在初始化之后）
  if (showBootSync) {
    return (
      <BootSync
        onComplete={handleBootSyncComplete}
        onError={handleBootSyncError}
      />
    );
  }

  // Phase 5: 根据当前视图渲染不同页面
  if (currentView === 'save-home') {
    return (
      <SaveCapsuleHome
        onSave={handleSaveCapsule}
        saveStatus={saveStatus}
        saveProgress={saveProgress}
        onShowLibrary={() => setCurrentView('library')}
      />
    );
  }

  // Phase 5.5: 胶囊库视图
  if (currentView === 'library') {
    return (
      <CapsuleLibrary
        capsules={capsuleList}
        onEdit={handleEditCapsule}
        onDelete={handleDeleteCapsule}
        onBack={handleBackToHome}
        refreshTrigger={libraryRefreshTrigger}
        onSyncComplete={loadCapsules}
      />
    );
  }

  return (
    <div className="min-h-screen flex flex-col p-4 md:p-8 relative">
      {/* 星空背景 */}
      <div className="starfield" />

      {/* 主内容 */}
      <div className="relative z-10 max-w-5xl mx-auto w-full">

        {/* 标题 */}
        <header className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center">
                  <Sparkles className="w-6 h-6 text-purple-400" />
                </div>
                <span>Synesth</span>
                <span className="text-xs font-normal text-zinc-600 bg-zinc-900/80 px-3 py-1.5 rounded-full border border-zinc-800">
                  AI 声景词典 v1.0
                </span>
              </h1>
              <p className="text-sm text-zinc-500">
                移动光标探索语义空间，点击词汇构建你的声音画像
              </p>
            </div>

            {/* 同步指示器 + 用户菜单 */}
            <div className="flex items-center gap-3">
              <SyncIndicator />
              <UserMenu />
            </div>
          </div>
        </header>

        {/* 透镜切换 Tab */}
        <div className="mb-8">
          <div className={clsx(
            "grid gap-3 bg-zinc-900/80 backdrop-blur-xl p-2 rounded-2xl border border-zinc-800 shadow-xl",
            Object.keys(lensConfig).length <= 3 ? "grid-cols-3" :
              Object.keys(lensConfig).length === 4 ? "grid-cols-4" :
                "grid-cols-3 sm:grid-cols-5"
          )}>
            {Object.values(lensConfig).map((lens) => {
              const Icon = ICON_MAP[lens.icon] || CircleDot;
              const isActive = activeLens === lens.id;
              return (
                <button
                  key={lens.id}
                  onClick={() => setActiveLens(lens.id)}
                  className={clsx(
                    'relative flex items-center justify-center gap-2 px-4 py-3 rounded-xl transition-all duration-300 font-medium',
                    isActive
                      ? 'text-white shadow-lg'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/5'
                  )}
                  style={isActive ? {
                    background: `linear-gradient(135deg, ${lens.accentColor}20, ${lens.accentColor}10)`,
                    boxShadow: `inset 0 0 0 1px ${lens.accentColor}40, 0 4px 12px ${lens.accentColor}20`
                  } : {
                    boxShadow: 'inset 0 0 0 1px transparent'
                  }}
                >
                  <Icon
                    className="w-5 h-5 flex-shrink-0"
                    style={{ color: isActive ? lens.accentColor : 'currentColor' }}
                  />
                  <span className="hidden sm:inline text-sm tracking-wide">
                    {lens.name?.split(' /')[0] || lens.id}
                  </span>
                  <span className="sm:hidden text-sm">
                    {lens.nameCn || lens.id}
                  </span>

                  {/* 活跃指示器 */}
                  {isActive && (
                    <div
                      className="absolute bottom-1 left-1/2 -translate-x-1/2 w-8 h-0.5 rounded-full"
                      style={{ backgroundColor: lens.accentColor }}
                    />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* 主体布局 */}
        <div className="flex flex-col lg:flex-row gap-6">

          {/* 左侧：向量空间画布 */}
          <div className="flex-1 flex flex-col gap-4">
            <div
              ref={containerRef}
              className="relative w-full aspect-square rounded-3xl overflow-hidden cursor-crosshair shadow-2xl border border-zinc-800 touch-none select-none group"
              onMouseDown={handleDragStart}
              onMouseMove={handleDragMove}
              onMouseUp={handleDragEnd}
              onMouseLeave={handleDragEnd}
              onTouchStart={handleDragStart}
              onTouchMove={handleDragMove}
              onTouchEnd={handleDragEnd}
              style={{
                boxShadow: `0 20px 60px -10px ${currentLens.accentColor}30, 0 0 0 1px ${currentLens.accentColor}10`
              }}
            >
              {/* 动态渐变背景 */}
              <div
                className="absolute inset-0 bg-gradient-to-br transition-all duration-700"
                style={{
                  background: `linear-gradient(135deg, ${currentLens.accentColor}15, transparent 50%, ${currentLens.accentColor}5)`
                }}
              />

              {/* 暗角 */}
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,rgba(0,0,0,0.8)_100%)]" />

              {/* 网格 */}
              <div className="absolute inset-0 vector-grid opacity-30" />

              {/* 渲染所有词汇点 */}
              {vectorData && vectorData[activeLens] && (
                vectorData[activeLens].points.map((point, idx) => {
                  const isHighlighted = suggestedWords.some(s => (s.id || s.word) === (point.id || point.word));
                  return (
                    <div
                      key={point.id || `${point.word}-${idx}`}
                      className={clsx('absolute w-2 h-2 rounded-full transition-all duration-200', isHighlighted ? 'highlighted' : '')}
                      style={{
                        left: `${point.x}%`,
                        top: `${point.y}%`,
                        transform: 'translate(-50%, -50%)',
                        opacity: isHighlighted ? 1 : 0.3,
                        backgroundColor: isHighlighted ? currentLens.accentColor : 'rgba(255,255,255,0.3)',
                        boxShadow: isHighlighted ? `0 0 20px ${currentLens.accentColor}, 0 0 40px ${currentLens.accentColor}40` : 'none',
                      }}
                    />
                  );
                })
              )}

              {/* 坐标轴标签 */}
              <div className="absolute top-3 left-1/2 -translate-x-1/2 text-[10px] md:text-xs font-bold text-white/90 uppercase bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-full whitespace-nowrap border border-white/10 shadow-lg">
                ▲ {currentLens.axis.top}
              </div>
              <div className="absolute bottom-3 left-1/2 -translate-x-1/2 text-[10px] md:text-xs font-bold text-white/90 uppercase bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-full whitespace-nowrap border border-white/10 shadow-lg">
                ▼ {currentLens.axis.bottom}
              </div>
              <div className="absolute left-2 top-1/2 -translate-y-1/2 flex items-center justify-center">
                <div className="-rotate-90 text-[10px] md:text-xs font-bold text-white/90 uppercase bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-full whitespace-nowrap border border-white/10 shadow-lg">
                  {currentLens.axis.left}
                </div>
              </div>
              <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center justify-center">
                <div className="rotate-90 text-[10px] md:text-xs font-bold text-white/90 uppercase bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-full whitespace-nowrap border border-white/10 shadow-lg">
                  {currentLens.axis.right}
                </div>
              </div>

              {/* 光标 */}
              <div
                className="absolute -translate-x-1/2 -translate-y-1/2 w-8 h-8 rounded-full pointer-events-none transition-all duration-75"
                style={{
                  left: `${cursorPos.x}%`,
                  top: `${cursorPos.y}%`,
                  backgroundColor: currentLens.accentColor,
                  boxShadow: `0 0 20px ${currentLens.accentColor}, 0 0 40px ${currentLens.accentColor}60, inset 0 0 10px rgba(255,255,255,0.3)`
                }}
              >
                <div
                  className="absolute inset-0 animate-ping rounded-full opacity-75"
                  style={{ backgroundColor: currentLens.accentColor }}
                />
                <div
                  className="absolute inset-2 rounded-full bg-white/50 blur-sm"
                />
              </div>

              {/* Phase 5.4: 已选标签的位置标记 */}
              {selectedTags.map((tag, idx) => {
                // 如果标签有坐标信息，显示位置标记
                if (tag.x !== undefined && tag.y !== undefined && tag.x !== null && tag.y !== null) {
                  return (
                    <div
                      key={`marker-${tag.word_id || tag.id || tag.word || idx}`}
                      className="absolute -translate-x-1/2 -translate-y-1/2 pointer-events-none transition-all duration-200"
                      style={{
                        left: `${tag.x}%`,
                        top: `${tag.y}%`,
                      }}
                      title={tag.zh || tag.word || tag.cn}
                    >
                      {/* 位置标记：外圈脉冲 + 内圈实心 */}
                      <div
                        className="w-4 h-4 rounded-full animate-pulse"
                        style={{
                          backgroundColor: currentLens.accentColor,
                          opacity: 0.3,
                          animation: 'ping 2s cubic-bezier(0, 0, 0.2, 1) infinite'
                        }}
                      />
                      <div
                        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 rounded-full border-2"
                        style={{ borderColor: currentLens.accentColor, backgroundColor: currentLens.accentColor }}
                      />
                    </div>
                  );
                }
                return null;
              })}
            </div>

            {/* 坐标显示 */}
            <div className="flex justify-between text-xs text-zinc-500 px-2 font-mono">
              <span>X: <span className="text-zinc-300">{Math.round(cursorPos.x)}</span></span>
              <span className="text-zinc-300 font-semibold">{currentLens.name}</span>
              <span>Y: <span className="text-zinc-300">{Math.round(cursorPos.y)}</span></span>
            </div>
          </div>

          {/* 右侧：推荐与操作 */}
          <div className="flex-1 flex flex-col gap-4 lg:max-w-md">

            {/* Phase 5.4: 嵌入标签按钮 - 允许保存空标签（删除所有标签） */}
            {currentCapsuleId && (
              <button
                onClick={handleLensComplete}
                className={clsx(
                  'w-full py-4 rounded-2xl font-bold text-sm flex items-center justify-center gap-3 transition-all border',
                  selectedTags.length === 0
                    ? 'bg-gradient-to-r from-red-500/80 to-orange-500/80 text-white border-red-400/30 shadow-lg shadow-red-500/20 hover:shadow-red-500/40 hover:-translate-y-0.5'
                    : 'bg-gradient-to-r from-purple-500 to-pink-500 text-white border-purple-400/30 shadow-lg shadow-purple-500/20 hover:shadow-purple-500/40 hover:-translate-y-0.5'
                )}
              >
                <Check className="w-5 h-5" />
                {selectedTags.length === 0 
                  ? `清除${currentLens.nameCn || currentLens.id}标签`
                  : `嵌入${currentLens.nameCn || currentLens.id}标签`
                }
                <span className="text-xs font-normal opacity-75">
                  ({selectedTags.length} 个已选)
                </span>
              </button>
            )}

            {/* 已选标签预览（精简版） */}
            {selectedTags.length > 0 && (
              <div className="bg-zinc-900/60 backdrop-blur-sm p-4 rounded-2xl border border-zinc-800">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-bold text-zinc-500 uppercase tracking-wider">已选择</span>
                  <button
                    onClick={clearTags}
                    className="text-xs text-zinc-600 hover:text-red-400 transition-colors"
                  >
                    清空
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {selectedTags.slice(0, 10).map((tag, idx) => {
                    const displayText = tag.zh || tag.word || tag.cn;
                    // 使用唯一标识符作为key
                    const uniqueKey = tag.word_id || tag.id || tag.word || idx;
                    return (
                      <span
                        key={uniqueKey}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-zinc-800 text-zinc-300 text-xs rounded-full border border-zinc-700 hover:border-zinc-600 transition-all"
                      >
                        {displayText}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleTag(tag);
                          }}
                          className="text-zinc-600 hover:text-white transition-colors ml-1"
                          title={`删除 ${displayText}`}
                        >
                          ×
                        </button>
                      </span>
                    );
                  })}
                  {selectedTags.length > 10 && (
                    <span className="text-xs text-zinc-600 px-3 py-1.5 bg-zinc-900/50 rounded-full border border-zinc-800">
                      +{selectedTags.length - 10} 更多...
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* 实时推荐 */}
            <div className="bg-zinc-900/60 backdrop-blur-sm p-5 rounded-2xl border border-zinc-800">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest flex items-center gap-2">
                  <Sparkles className="w-4 h-4" style={{ color: currentLens.accentColor }} />
                  推荐标签
                </h3>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] text-zinc-600 font-mono">Radius: {selectionRadius}</span>
                  <input
                    type="range"
                    min="5"
                    max="50"
                    value={selectionRadius}
                    onChange={(e) => setSelectionRadius(parseInt(e.target.value))}
                    className="w-20 h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer"
                    style={{ accentColor: currentLens.accentColor }}
                  />
                </div>
              </div>
              <div className="flex flex-wrap gap-2 min-h-[100px]">
                {suggestedWords.length === 0 ? (
                  <p className="text-zinc-600 text-sm italic w-full text-center py-4">移动光标获取推荐词汇...</p>
                ) : (
                  suggestedWords.map((item, idx) => {
                    // 使用与toggleTag相同的key策略
                    const itemKey = item.word_id || item.id || item.word;
                    const isSelected = selectedTags.some(t => {
                      const tagKey = t.word_id || t.id || t.word;
                      return tagKey === itemKey;
                    });
                    return (
                      <button
                        key={itemKey}
                        onClick={() => toggleTag(item)}
                        className={clsx(
                          'inline-flex items-center gap-2 px-4 py-2 text-sm rounded-xl font-medium transition-all duration-200 animate-[fadeIn_0.3s_ease]',
                          isSelected
                            ? 'text-white shadow-lg'
                            : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
                        )}
                        style={{
                          animationDelay: `${idx * 30}ms`,
                          ...(isSelected ? {
                            background: `linear-gradient(135deg, ${currentLens.accentColor}30, ${currentLens.accentColor}15)`,
                            boxShadow: `inset 0 0 0 1px ${currentLens.accentColor}40, 0 4px 12px ${currentLens.accentColor}20`
                          } : {
                            background: 'transparent',
                            boxShadow: 'inset 0 0 0 1px transparent'
                          })
                        }}
                      >
                        {item.zh}
                        <span className="text-zinc-600 ml-1.5 text-xs">({item.word})</span>
                      </button>
                    );
                  })
                )}
              </div>
            </div>

          </div>
        </div>

        {/* 底部统计 */}
        <footer className="mt-8 text-center text-xs text-zinc-600">
          <p>
            当前透镜: <span className="text-zinc-400 font-medium">{currentLens.name}</span>
            {vectorData && vectorData[activeLens] && (
              <> · 词库: <span className="text-zinc-400 font-medium">{vectorData[activeLens].points.length} 词</span></>
            )}
          </p>
        </footer>
      </div>

      {/* 导出向弹窗 */}
      {showExportWizard && (
        <CapsuleExportWizard
          onClose={() => setShowExportWizard(false)}
          onSuccess={(importedCapsule) => {
            console.log('========================================');
            console.log('🎉 导出并导入成功！');
            console.log('========================================');
            console.log('🆔 导入的胶囊 ID:', importedCapsule.id);
            console.log('📦 胶囊名称:', importedCapsule.name);
            console.log('🏷️  胶囊类型:', importedCapsule.capsule_type);
            console.log('🎵 预览音频:', importedCapsule.preview_audio);

            // 更新当前胶囊状态
            setCurrentCapsuleId(importedCapsule.id);
            setCurrentCapsule(importedCapsule);

            setShowExportWizard(false);
          }}
          currentCapsuleType={currentCapsule?.capsule_type}
          currentCapsuleId={currentCapsuleId}
        />
      )}

      {/* Phase 5.4: 多棱镜完成对话框 */}
      <LensCompleteDialog
        isOpen={showCompleteDialog}
        lensName={activeLens}
        lensConfig={lensConfig}
        selectedTags={selectedTags}
        completedLenses={completedLenses}
        onContinue={handleContinueSelection}
        onFinish={handleFinishAllTags}
      />

      {/* 调试面板 - 已隐藏 */}
      {/* <DebugStatePanel
        currentCapsuleId={currentCapsuleId}
        currentCapsule={currentCapsule}
        previewAudio={previewAudio}
        currentCapsuleType={currentCapsule?.capsule_type}
        exportStatus={saveStatus}
      /> */}
    </div>
  );
}

