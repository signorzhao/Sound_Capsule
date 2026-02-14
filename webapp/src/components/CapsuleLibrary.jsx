import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Search, Grid3X3, List, Network, Trash2, Edit, X, Play, Pause,
  Download, HeadphonesIcon, User, Flame, Zap,
  Sparkles, Music, Activity, Box, Volume2, Maximize2, MousePointer2,
  Radio, Headphones, Guitar, Piano, Mic, Bell, Signal, Heart, Timer, Clock,
  Target, Star, Sun, Moon, Snowflake, Cloud, CheckCircle, Loader, HardDrive
} from 'lucide-react';
import { useToast } from './Toast';
import UserMenu from './UserMenu';
import SyncIndicator from './SyncIndicator';
import DownloadProgressDialog from './DownloadProgressDialog';
import SmartActionButton from './SmartActionButton';
import DownloadConfirmModal from './DownloadConfirmModal';
import CloudSyncIcon from './CloudSyncIcon';
import { getTagDisplayText } from '../utils/tagUtils';
import i18n from '../i18n';
import './CapsuleLibrary.css';

// 图标映射表 - 用于动态加载图标
const ICON_COMPONENTS = {
  Sparkles, Flame, Music, Activity, Box,
  Zap, Radio, Headphones, Guitar,
  Piano, Mic, Volume2, Bell,
  Signal, Heart, Timer, Clock,
  Target, Star, Sun, Moon, Snowflake
};

/**
 * 胶囊库组件 - 重构版
 *
 * 支持多种视图模式、搜索、过滤、胶囊管理
 * 使用真实的数据库数据
 */

function CapsuleLibrary({ capsules = [], onEdit, onDelete, onBack, onImport, onImportToReaper, refreshTrigger = 0, onSyncComplete }) {
  const { t } = useTranslation();
  const toast = useToast();

  // 胶囊类型数据（从API动态加载）
  const [capsuleTypes, setCapsuleTypes] = useState([]);

  // 视图模式: 'list' | 'network'
  const [viewMode, setViewMode] = useState('list');

  // 搜索和过滤
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState('all');

  // 管理模式
  const [isAdmin, setIsAdmin] = useState(false);

  // 胶囊打开状态
  const [openCapsuleId, setOpenCapsuleId] = useState(null);

  // 音频播放器
  const [nowPlaying, setNowPlaying] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0); // 仅用于首次加载时显示 --:--，loadedmetadata 后更新一次
  const audioRef = useRef(null);
  const progressRef = useRef(0);
  const progressBarRef = useRef(null);
  const progressTrackRef = useRef(null);
  const currentTimeDisplayRef = useRef(null); // 直接更新 DOM，避免 timeupdate 触发重渲染导致卡顿
  const durationDisplayRef = useRef(null);
  const autoPlayRef = useRef(false);

  // 元数据缓存（每个胶囊的 metadata.json）
  const [metadataCache, setMetadataCache] = useState({});

  // 标签缓存（每个胶囊的棱镜标签）
  const [tagsCache, setTagsCache] = useState({});

  // 监听 refreshTrigger 变化，清除 tags 和 metadata 缓存
  useEffect(() => {
    if (refreshTrigger > 0) {
      console.log('清除 tags 和 metadata 缓存，触发器:', refreshTrigger);
      setTagsCache({});
      setMetadataCache({}); // 🔥 同时清除 metadata 缓存
    }
  }, [refreshTrigger]);

  // 下载状态管理 (Phase B.3)
  const [downloadDialog, setDownloadDialog] = useState(null); // { capsuleId, capsuleName, taskStatus }
  const [assetStatusCache, setAssetStatusCache] = useState({}); // 资产状态缓存

  // JIT 弹窗状态
  const [modalCapsule, setModalCapsule] = useState(null); // 当前显示弹窗的胶囊

  // 单个胶囊上传中状态（用于提示与防重复点击）
  const [uploadingCapsules, setUploadingCapsules] = useState({});

  // 默认胶囊类型（防御性降级）
  const DEFAULT_CAPSULE_TYPES = [
    { id: 'magic', name: 'MAGIC', name_cn: '魔法', icon: 'Sparkles', color: '#8B5CF6', gradient: 'linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%)' },
    { id: 'impact', name: 'IMPACT', name_cn: '打击', icon: 'Flame', color: '#EF4444', gradient: 'linear-gradient(135deg, #EF4444 0%, #F59E0B 100%)' },
    { id: 'atmosphere', name: 'ATMOSPHERE', name_cn: '环境', icon: 'Music', color: '#10B981', gradient: 'linear-gradient(135deg, #10B981 0%, #06B6D4 100%)' }
  ];

  // 加载胶囊类型数据
  const loadCapsuleTypes = async () => {
    try {
      const response = await fetch('http://localhost:5002/api/capsule-types');
      const data = await response.json();
      if (data.success && data.types && data.types.length > 0) {
        setCapsuleTypes(data.types);
        console.log('加载胶囊类型:', data.types.length, '个');
      } else {
        console.warn('胶囊类型数据为空，使用默认类型');
        setCapsuleTypes(DEFAULT_CAPSULE_TYPES);
      }
    } catch (error) {
      console.error('加载胶囊类型失败，使用默认类型:', error);
      setCapsuleTypes(DEFAULT_CAPSULE_TYPES);
    }
  };

  // 组件加载时获取胶囊类型
  useEffect(() => {
    loadCapsuleTypes();
  }, []);

  // 根据胶囊类型ID获取图标组件
  const getTypeIcon = (typeId) => {
    const type = capsuleTypes.find(t => t.id === typeId);
    if (!type || !type.icon) {
      return ICON_COMPONENTS.Sparkles; // 默认图标
    }
    return ICON_COMPONENTS[type.icon] || ICON_COMPONENTS.Sparkles;
  };

  // 根据胶囊类型ID获取颜色配置
  const getTypeColors = (typeId) => {
    const type = capsuleTypes.find(t => t.id === typeId);
    if (!type) {
      return { top: '#8b5cf6', bottom: '#4c1d95' }; // 默认颜色
    }

    // 从 gradient 中提取颜色
    // gradient 格式: "linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%)"
    const colorMatch = type.gradient.match(/#[A-Fa-f0-9]{6}/g);
    if (colorMatch && colorMatch.length >= 2) {
      return { top: colorMatch[0], bottom: colorMatch[1] };
    }

    return { top: type.color, bottom: type.color };
  };

  // 根据胶囊类型ID获取名称（按当前语言）
  const getTypeName = (typeId) => {
    const type = capsuleTypes.find(t => t.id === typeId);
    if (!type) return typeId;
    const isEn = i18n.language === 'en' || i18n.language?.startsWith('en');
    return isEn ? (type.name || typeId) : (type.name_cn || type.name || typeId);
  };

  // Phase B.3: 获取胶囊资产状态
  const getAssetStatus = async (capsuleId) => {
    if (assetStatusCache[capsuleId]) {
      return assetStatusCache[capsuleId];
    }

    try {
      const { authFetch } = await import('../utils/apiClient.js');
      const response = await authFetch(`http://localhost:5002/api/capsules/${capsuleId}/asset-status`);
      if (!response.ok) {
        // 如果端点不存在，回退到旧的逻辑
        return { asset_status: 'local', file_sync_status: 'full' };
      }
      const data = await response.json();
      const status = data.asset_status || {};

      // 缓存状态
      setAssetStatusCache(prev => ({
        ...prev,
        [capsuleId]: status
      }));

      return status;
    } catch (error) {
      console.error('获取资产状态失败:', error);
      return { asset_status: 'local', file_sync_status: 'full' };
    }
  };

  // Phase B.3: 获取文件状态徽章配置
  const getFileStatusBadge = (capsule) => {
    const status = assetStatusCache[capsule.id];
    if (!status) {
      return {
        icon: HardDrive,
        color: 'gray',
        text: t('assetStatus.local'),
        bgColor: 'bg-gray-900/50',
        borderColor: 'border-gray-700',
        textColor: 'text-gray-400'
      };
    }

    const assetStatus = status.asset_status || 'local';
    const downloadProgress = status.download_progress || 0;

    if (downloadProgress > 0 && downloadProgress < 100 && assetStatus === 'downloading') {
      return {
        icon: Loader,
        color: 'blue',
        text: t('assetStatus.downloadingPct', { pct: downloadProgress }),
        bgColor: 'bg-blue-900/30',
        borderColor: 'border-blue-700',
        textColor: 'text-blue-400',
        animated: true
      };
    }

    switch (assetStatus) {
      case 'full':
        return {
          icon: CheckCircle,
          color: 'green',
          text: t('assetStatus.downloaded'),
          bgColor: 'bg-green-900/30',
          borderColor: 'border-green-700',
          textColor: 'text-green-400'
        };
      case 'downloading':
        return {
          icon: Loader,
          color: 'blue',
          text: t('assetStatus.downloading'),
          bgColor: 'bg-blue-900/30',
          borderColor: 'border-blue-700',
          textColor: 'text-blue-400',
          animated: true
        };
      case 'cloud_only':
        return {
          icon: Cloud,
          color: 'blue',
          text: t('assetStatus.cloud'),
          bgColor: 'bg-blue-900/20',
          borderColor: 'border-blue-800',
          textColor: 'text-blue-400'
        };
      case 'local':
      default:
        return {
          icon: HardDrive,
          color: 'gray',
          text: t('assetStatus.local'),
          bgColor: 'bg-gray-900/50',
          borderColor: 'border-gray-700',
          textColor: 'text-gray-400'
        };
    }
  };

  // Phase B.3: 检查是否需要下载
  const checkNeedsDownload = async (capsule) => {
    const status = await getAssetStatus(capsule.id);
    const assetStatus = status.asset_status || 'local';

    // 如果不是 'full' 状态，则需要下载
    return assetStatus !== 'full' && assetStatus !== 'local';
  };

  // 加载单个胶囊的 metadata.json
  const loadCapsuleMetadata = async (capsule) => {
    if (metadataCache[capsule.id]) {
      return metadataCache[capsule.id];
    }

    try {
      const response = await fetch(`http://localhost:5002/api/capsules/${capsule.id}/metadata`);
      if (!response.ok) {
        // 404 是正常的，很多胶囊没有 metadata
        return null;
      }
      const data = await response.json();

      // API 返回格式: {success: true, metadata: {...}}
      const metadata = data.metadata || null;

      // 更新缓存 - 只缓存 metadata 部分
      setMetadataCache(prev => ({
        ...prev,
        [capsule.id]: metadata
      }));

      return metadata;
    } catch (error) {
      // 静默处理错误
      return null;
    }
  };

  // 组件加载时，优先使用列表返回的 metadata，只有缺失的才调用 API
  // 🔥 添加 refreshTrigger 依赖，确保刷新时重新加载
  useEffect(() => {
    const loadMetadata = async () => {
      console.log('开始加载胶囊 metadata，胶囊数量:', capsules.length, '刷新触发器:', refreshTrigger);

      // 统计来源
      let fromList = 0;
      let missingMetadata = [];

      // 🔥 每次刷新时从空缓存开始，避免闭包问题
      const newCache = {};

      for (const capsule of capsules) {
        if (capsule.metadata) {
          // 列表已返回 metadata，直接使用
          newCache[capsule.id] = capsule.metadata;
          fromList++;
        } else {
          // 🔥 记录缺失 metadata 的胶囊
          missingMetadata.push({ id: capsule.id, name: capsule.name });
        }
      }

      // 批量更新缓存（从列表获取的）
      setMetadataCache(newCache);

      console.log(`Metadata 加载完成: 从列表=${fromList}, 缺失=${missingMetadata.length}`);
      if (missingMetadata.length > 0) {
        console.warn('⚠️ 以下胶囊缺少 metadata:', missingMetadata);
      }
    };

    if (capsules.length > 0) {
      loadMetadata();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [capsules, refreshTrigger]);

  // Phase B.3: 加载资产状态（轻量级）
  useEffect(() => {
    const loadAssetStatuses = async () => {
      for (const capsule of capsules) {
        try {
          if (!assetStatusCache[capsule.id]) {
            await getAssetStatus(capsule.id);
          }
        } catch (error) {
          console.error('加载资产状态失败:', capsule.id, error);
        }
      }
    };

    if (capsules.length > 0) {
      loadAssetStatuses();
    }
  }, [capsules]);

  // 当切换到列表视图时，懒加载 tags（避免阻塞渲染）
  // 🔥 修复闭包问题：从 capsules 数据直接获取 tags，不依赖旧缓存
  useEffect(() => {
    if (viewMode === 'list' && capsules.length > 0) {
      const loadTagsForList = async () => {
        console.log('列表视图：开始加载胶囊 tags，刷新触发器:', refreshTrigger);

        // 🔥 每次刷新时从空缓存开始，直接使用 capsules 中的 tags
        let fromList = 0;
        const newCache = {};
        
        for (const capsule of capsules) {
          if (capsule.tags && capsule.tags.length > 0) {
            // 列表已返回 tags，转换格式后直接使用
            const formattedTags = {};
            for (const tag of capsule.tags) {
              const lens = tag.lens;
              if (!formattedTags[lens]) {
                formattedTags[lens] = [];
              }
              formattedTags[lens].push({
                word_id: tag.word_id,
                word_cn: tag.word_cn,
                word_en: tag.word_en,
                x: tag.x,
                y: tag.y
              });
            }
            newCache[capsule.id] = formattedTags;
            fromList++;
          }
        }

        // 批量更新缓存（从列表获取的）
        setTagsCache(newCache);
        console.log(`Tags 从列表获取: ${fromList} 个`);

        // 只加载还没有 tags 的胶囊
        const capsulesToLoad = capsules.filter(
          capsule => !newCache[capsule.id]
        );

        if (capsulesToLoad.length === 0) {
          console.log('列表视图：所有 tags 已加载');
          return;
        }

        // 并发加载所有 tags，但使用 Promise.allSettled 避免单个失败影响全部
        const promises = capsulesToLoad.map(async (capsule) => {
          try {
            const response = await fetch(`http://localhost:5002/api/capsules/${capsule.id}/tags`);

            if (!response.ok) {
              console.warn(`加载胶囊 ${capsule.id} tags 失败: HTTP ${response.status}`);
              setTagsCache(prev => ({ ...prev, [capsule.id]: null }));
              return;
            }

            const data = await response.json();
            const tags = data.tags || {};

            // 验证 tags 格式
            if (typeof tags !== 'object' || tags === null) {
              console.warn(`胶囊 ${capsule.id} tags 格式无效`);
              setTagsCache(prev => ({ ...prev, [capsule.id]: null }));
              return;
            }

            // 更新缓存
            setTagsCache(prev => ({
              ...prev,
              [capsule.id]: tags
            }));
          } catch (error) {
            console.warn(`加载胶囊 ${capsule.id} tags 失败:`, error.message);
            setTagsCache(prev => ({ ...prev, [capsule.id]: null }));
          }
        });

        await Promise.allSettled(promises);
        console.log('列表视图：所有胶囊 tags 加载完成');
      };

      loadTagsForList();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode, capsules, refreshTrigger]); // 🔥 移除 tagsCache 依赖，避免无限循环

  // 过滤后的胶囊列表
  const filteredCapsules = useMemo(() => {
    return capsules.filter(capsule => {
      // 类型过滤
      if (selectedType !== 'all' && capsule.capsule_type !== selectedType) {
        return false;
      }

      // 搜索过滤 (搜索文件夹名、关键词)
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const searchableText = [
          capsule.name,
          capsule.keywords,
          capsule.capsule_type
        ].join(' ').toLowerCase();

        return searchableText.includes(query);
      }

      return true;
    });
  }, [capsules, searchQuery, selectedType]);

  // 统计信息
  const stats = useMemo(() => {
    const typeCounts = capsules.reduce((acc, capsule) => {
      const type = capsule.capsule_type || 'unknown';
      acc[type] = (acc[type] || 0) + 1;
      return acc;
    }, {});

    return {
      total: capsules.length,
      ...typeCounts
    };
  }, [capsules]);

  // 格式化时间
  const formatTime = (timestamp) => {
    if (!timestamp) return '未知时间';

    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins}分钟前`;
    if (diffHours < 24) return `${diffHours}小时前`;
    if (diffDays < 7) return `${diffDays}天前`;

    return date.toLocaleDateString('zh-CN');
  };

  // 格式化文件大小
  const formatFileSize = (bytes) => {
    if (!bytes) return '未知';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    return `${size.toFixed(1)} ${units[unitIndex]}`;
  };

  // 提取用户名从文件夹名
  const extractUserInfo = (capsule) => {
    // 文件夹名格式: {type}_{user}_{date}_{time}
    // 例如: impact_ianzhao_20260104_222425
    const parts = capsule.name.split('_');
    if (parts.length >= 2) {
      return { username: parts[1], hasUser: true };
    }
    // project_name_theme_name 格式
    if (capsule.project_name && capsule.theme_name) {
      return { username: '未知', project: capsule.project_name, theme: capsule.theme_name, hasUser: true };
    }
    return { username: '未知', hasUser: false };
  };

  // 音频播放控制 - 只在 isPlaying 改变时触发
  useEffect(() => {
    if (audioRef.current) {
      if (isPlaying) {
        // 等待音频元素准备好
        const playPromise = audioRef.current.play();
        if (playPromise !== undefined) {
          playPromise.catch(err => {
            // 忽略 AbortError，这是正常的切换音频时的中断
            if (err.name !== 'AbortError') {
              console.error('播放失败:', err);
              setIsPlaying(false);
            }
          });
        }
      } else {
        audioRef.current.pause();
      }
    }
  }, [isPlaying]); // 移除 nowPlaying 依赖

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handleTimeUpdate = () => {
      if (audio.duration) {
        const newProgress = (audio.currentTime / audio.duration) * 100;
        progressRef.current = newProgress;
        if (progressBarRef.current) progressBarRef.current.style.width = `${newProgress}%`;
        if (currentTimeDisplayRef.current) {
          const m = Math.floor(audio.currentTime / 60);
          const s = Math.floor(audio.currentTime % 60);
          currentTimeDisplayRef.current.textContent = `${m}:${s.toString().padStart(2, '0')}`;
        }
      }
    };

    const handleLoadedMetadata = () => {
      setDuration(audio.duration);
      if (durationDisplayRef.current) {
        const m = Math.floor(audio.duration / 60);
        const s = Math.floor(audio.duration % 60);
        durationDisplayRef.current.textContent = `${m}:${s.toString().padStart(2, '0')}`;
      }
    };

    const handleEnded = () => {
      setIsPlaying(false);
      progressRef.current = 0;
      if (progressBarRef.current) progressBarRef.current.style.width = '0%';
      if (currentTimeDisplayRef.current) currentTimeDisplayRef.current.textContent = '0:00';
    };

    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('ended', handleEnded);

    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('ended', handleEnded);
    };
  }, [nowPlaying]);

  // 播放音频
  const handlePlay = (capsule) => {
    if (nowPlaying?.id === capsule.id) {
      // 切换播放/暂停
      setIsPlaying(!isPlaying);
    } else {
      // 播放新的胶囊
      autoPlayRef.current = true; // 标记需要自动播放
      setNowPlaying(capsule);
      setIsPlaying(true);
      progressRef.current = 0;
      setDuration(0);
      if (currentTimeDisplayRef.current) currentTimeDisplayRef.current.textContent = '0:00';
      if (durationDisplayRef.current) durationDisplayRef.current.textContent = '--:--';
      if (progressBarRef.current) progressBarRef.current.style.width = '0%';
    }
  };

  // 点击进度条跳转
  const handleProgressClick = (e) => {
    const audio = audioRef.current;
    const track = progressTrackRef.current;
    if (!audio || !track || !audio.duration) return;
    const rect = track.getBoundingClientRect();
    const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    audio.currentTime = percent * audio.duration;
    progressRef.current = percent * 100;
    if (progressBarRef.current) progressBarRef.current.style.width = `${percent * 100}%`;
    if (currentTimeDisplayRef.current) {
      const m = Math.floor(audio.currentTime / 60);
      const s = Math.floor(audio.currentTime % 60);
      currentTimeDisplayRef.current.textContent = `${m}:${s.toString().padStart(2, '0')}`;
    }
  };

  // 获取音频URL（仅在 nowPlaying 变化时更新，避免重渲染导致 src 频繁变化中断播放）
  const audioUrl = useMemo(() => {
    if (!nowPlaying) return '';
    const apiBase = window.location.hostname === 'localhost'
      ? 'http://localhost:5002'
      : 'http://localhost:5002';
    return `${apiBase}/api/capsules/${nowPlaying.id}/preview`;
  }, [nowPlaying?.id]);

  // Phase B.3: JIT 智能点击处理
  const handleSmartClick = async (capsule) => {
    // 确定胶囊的当前状态（直接从 capsule 对象读取，不调用 API）
    const status = capsule.asset_status || capsule.cloud_status || 'cloud_only';

    console.log('[JIT] 胶囊状态:', capsule.name, 'status:', status);

    // 1. 如果已同步（包括 synced, local, full），直接打开 REAPER
    if (status === 'synced' || status === 'local' || status === 'full') {
      await openCapsuleInReaper(capsule, false);
      return;
    }

    // 2. 如果正在下载，显示提示
    if (status === 'downloading') {
      toast.info(t('librarySync.downloadingPleaseWait'));
      return;
    }

    // 3. 否则 (cloud_only 或 partial)，弹出决策框
    setModalCapsule(capsule);
  };

  // 用户确认下载
  const handleDownloadConfirm = async () => {
    if (!modalCapsule) return;

    setModalCapsule(null); // 关闭弹窗

    try {
      // 调用后端开始下载完整资源
      const response = await fetch(`http://localhost:5002/api/capsules/${modalCapsule.id}/download-assets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const result = await response.json();

      if (result.success) {
        // 显示下载进度对话框
        setDownloadDialog({
          capsuleId: modalCapsule.id,
          capsuleName: modalCapsule.name || modalCapsule.capsule_type,
          taskStatus: 'pending'
        });
      } else {
        toast.error(t('librarySync.createDownloadTaskFailed') + ': ' + result.error);
      }
    } catch (error) {
      console.error('创建下载任务失败:', error);
      toast.error(t('librarySync.createDownloadTaskFailed'));
    }
  };

  // 用户选择仅打开 RPP（离线模式）
  const handleOpenRppOnly = async () => {
    if (!modalCapsule) return;

    const capsule = modalCapsule;
    setModalCapsule(null); // 关闭弹窗
    await openCapsuleInReaper(capsule, true); // skipWavCheck = true
  };

  // 旧函数保持兼容
  const handleImportToReaper = handleSmartClick;

  // Phase G: 云同步处理函数
  const handleCloudSync = async (capsule) => {
    const status = capsule.cloud_status;

    const startUploadProgressPoll = async (capsuleId, toastId, onDone) => {
      const { authFetch } = await import('../utils/apiClient.js');
      let active = true;
      let doneCalled = false;

      const pollOnce = async () => {
        if (!active) return;
        try {
          const response = await authFetch(`http://localhost:5002/api/sync/upload-progress?capsule_id=${capsuleId}`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
          });
          if (!response.ok) {
            return;
          }
          const result = await response.json();
          const data = result.data;
          if (!data) return;

          const percentText = typeof data.percent === 'number' ? ` ${data.percent}%` : '';
          const fileText = data.current_file ? ` · ${data.current_file}` : '';
          const message = `${data.stage || t('librarySync.uploadStage')}${fileText}${percentText}`;

          if (data.status === 'completed') {
            toast.update(toastId, data.message || t('librarySync.uploadComplete'), 'success');
            if (!doneCalled && onDone) {
              doneCalled = true;
              onDone('completed');
            }
            active = false;
            return;
          }
          if (data.status === 'error') {
            toast.update(toastId, data.message || t('librarySync.uploadFailed'), 'error');
            if (!doneCalled && onDone) {
              doneCalled = true;
              onDone('error');
            }
            active = false;
            return;
          }

          toast.update(toastId, message, 'info', 0);
        } catch (error) {
          // 忽略轮询失败，避免打断上传
        }
      };

      const timer = setInterval(pollOnce, 1500);
      pollOnce();

      return () => {
        active = false;
        clearInterval(timer);
      };
    };
    
    if (status === 'local') {
      // 状态 1: 需上传 - 上传元数据到云端
      // 🔥 将变量声明移到 try 块外部，确保 catch 和 finally 中可访问
      let toastId = null;
      let toastFinalized = false;
      let stopProgressPoll = null;
      
      try {
        if (uploadingCapsules[capsule.id]) {
          toast.info(t('librarySync.uploadingPleaseWait'));
          return;
        }
        setUploadingCapsules(prev => ({ ...prev, [capsule.id]: true }));
        toastId = toast.loading(t('librarySync.uploadingCapsule', { name: capsule.name }));
        const { authFetch } = await import('../utils/apiClient.js');
        
        // 使用轻量级同步端点进行上传
        const requestPromise = authFetch('http://localhost:5002/api/sync/lightweight', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            include_previews: true,
            capsule_ids: [capsule.id] // 只同步指定的胶囊
          })
        });
        stopProgressPoll = await startUploadProgressPoll(capsule.id, toastId, (status) => {
          if (status === 'completed') {
            window.dispatchEvent(new CustomEvent('sync-completed'));
            onSyncComplete && onSyncComplete();
          }
        });
        const response = await requestPromise;
        
        const isOk = response.ok || response.status === 207;
        if (isOk) {
          const result = await response.json();
          if (result.success) {
            toast.update(toastId, t('librarySync.uploadedToCloud'), 'success');
            toastFinalized = true;
            
            // 🔥 清除该胶囊的状态缓存，强制 UI 刷新
            setAssetStatusCache(prev => {
              const newCache = { ...prev };
              delete newCache[capsule.id];
              return newCache;
            });
            
            // 手动刷新胶囊列表
            window.dispatchEvent(new CustomEvent('sync-completed'));
            onSyncComplete && onSyncComplete();
          } else {
            const message = result.error || t('librarySync.syncWarning');
            const type = response.status === 207 ? 'warning' : 'error';
            toast.update(toastId, t('librarySync.uploadCompleteWithMessage', { message }), type);
            toastFinalized = true;
            if (response.status === 207) {
              window.dispatchEvent(new CustomEvent('sync-completed'));
              onSyncComplete && onSyncComplete();
            }
          }
        } else {
          toast.update(toastId, t('librarySync.uploadFailedHttp', { status: response.status }), 'error');
          toastFinalized = true;
        }
      } catch (error) {
        console.error('上传失败:', error);
        if (toastId) {
          toast.update(toastId, t('librarySync.uploadFailedError', { message: error.message }), 'error');
          toastFinalized = true;
        } else {
          toast.error(t('librarySync.uploadFailedError', { message: error.message }));
        }
      } finally {
        if (stopProgressPoll) stopProgressPoll();
        if (toastId && !toastFinalized) {
          toast.dismiss(toastId);
        }
        setUploadingCapsules(prev => ({ ...prev, [capsule.id]: false }));
      }
    } else if (status === 'remote') {
      // 状态 2: 需下载 - 从云端拉取最新元数据
      try {
        const { authFetch } = await import('../utils/apiClient.js');
        
        // 使用轻量级同步端点拉取最新数据
        const response = await authFetch('http://localhost:5002/api/sync/lightweight', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            include_previews: true 
          })
        });
        
        if (response.ok) {
          const result = await response.json();
          if (result.success) {
            toast.success(t('librarySync.syncedCloudData'));
            // 刷新胶囊列表
            // window.location.reload();
            console.error("🛑 [DEBUG] 拦截到重启请求（下载同步后刷新）");
            // 手动刷新胶囊列表而不是重启整个应用
            window.dispatchEvent(new CustomEvent('sync-completed'));
            onSyncComplete && onSyncComplete();
          } else {
            toast.error(t('librarySync.syncFailedError', { message: result.error || t('librarySync.unknownError') }));
          }
        } else {
          toast.error(t('librarySync.syncFailedHttp', { status: response.status }));
        }
      } catch (error) {
        console.error('同步失败:', error);
        toast.error(t('librarySync.syncFailedError', { message: error.message }));
      }
    } else if (status === 'synced') {
      // 状态 3: 已同步 - 强制重新上传（用于修复文件缺失问题）
      // 🔥 将变量声明移到 try 块外部，确保 catch 和 finally 中可访问
      let toastId = null;
      let toastFinalized = false;
      let stopProgressPoll = null;
      
      try {
        if (uploadingCapsules[capsule.id]) {
          toast.info(t('librarySync.uploadingPleaseWait'));
          return;
        }
        setUploadingCapsules(prev => ({ ...prev, [capsule.id]: true }));
        toastId = toast.loading(t('librarySync.reuploadingCapsule', { name: capsule.name }));
        const { authFetch } = await import('../utils/apiClient.js');

        // 使用轻量级同步端点进行强制上传
        const requestPromise = authFetch('http://localhost:5002/api/sync/lightweight', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            include_previews: true,
            capsule_ids: [capsule.id] // 强制上传指定的胶囊
          })
        });
        stopProgressPoll = await startUploadProgressPoll(capsule.id, toastId, (status) => {
          if (status === 'completed') {
            window.dispatchEvent(new CustomEvent('sync-completed'));
            onSyncComplete && onSyncComplete();
          }
        });
        const response = await requestPromise;

        const isOk = response.ok || response.status === 207;
        if (isOk) {
          const result = await response.json();
          if (result.success) {
            toast.update(toastId, t('librarySync.reuploadedToCloud'), 'success');
            toastFinalized = true;
            
            // 🔥 清除该胶囊的状态缓存，强制 UI 刷新
            setAssetStatusCache(prev => {
              const newCache = { ...prev };
              delete newCache[capsule.id];
              return newCache;
            });
            
            // 刷新胶囊列表
            window.dispatchEvent(new CustomEvent('sync-completed'));
            onSyncComplete && onSyncComplete();
          } else {
            const message = result.error || t('librarySync.syncWarning');
            const type = response.status === 207 ? 'warning' : 'error';
            toast.update(toastId, t('librarySync.reuploadCompleteWithMessage', { message }), type);
            toastFinalized = true;
            if (response.status === 207) {
              window.dispatchEvent(new CustomEvent('sync-completed'));
              onSyncComplete && onSyncComplete();
            }
          }
        } else {
          toast.update(toastId, t('librarySync.reuploadFailedHttp', { status: response.status }), 'error');
          toastFinalized = true;
        }
      } catch (error) {
        console.error('重新上传失败:', error);
        if (toastId) {
          toast.update(toastId, t('librarySync.reuploadFailedError', { message: error.message }), 'error');
          toastFinalized = true;
        } else {
          toast.error(t('librarySync.reuploadFailedError', { message: error.message }));
        }
      } finally {
        if (stopProgressPoll) stopProgressPoll();
        if (toastId && !toastFinalized) {
          toast.dismiss(toastId);
        }
        setUploadingCapsules(prev => ({ ...prev, [capsule.id]: false }));
      }
    } else {
      // 未知状态
      toast.info(t('librarySync.cloudStatusUnknown'));
    }
  };

  // 打开胶囊（内部函数 - 使用 API）
  const openCapsuleInReaper = async (capsule, skipWavCheck) => {
    if (onImportToReaper) {
      await onImportToReaper(capsule);
    } else {
      // 默认实现：调用API
      try {
        const response = await fetch(`http://localhost:5002/api/capsules/${capsule.id}/open`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ skip_wav_check: skipWavCheck })
        });
        const result = await response.json();
        if (result.success) {
          toast.success(t('librarySync.openedInReaper'));
        } else {
          toast.error(t('librarySync.openFailed') + ': ' + result.error);
        }
      } catch (error) {
        console.error('导入失败:', error);
        toast.error(t('librarySync.importFailed'));
      }
    }
  };

  // 下载完成回调
  const handleDownloadComplete = () => {
    toast.success(t('librarySync.downloadCompleteOpeningReaper'));
    if (downloadDialog) {
      const capsuleId = downloadDialog.capsuleId;
      const capsule = capsules.find(c => c.id === capsuleId);
      
      // 🔥 清除该胶囊的状态缓存，强制重新获取
      setAssetStatusCache(prev => {
        const newCache = { ...prev };
        delete newCache[capsuleId];
        return newCache;
      });
      
      // 🔥 重新获取该胶囊的状态
      getAssetStatus(capsuleId);
      
      // 🔥 触发父组件刷新（如果提供了回调）
      if (onSyncComplete) {
        onSyncComplete();
      }
      
      if (capsule) {
        openCapsuleInReaper(capsule, false);
      }
    }
    setDownloadDialog(null);
  };

  // 胶囊卡片组件 - 使用真正的 3D 胶囊设计
  const CapsuleCard = ({ capsule, isOpen, onClick }) => {
    const typeInfo = getTypeColors(capsule.capsule_type);
    const Icon = getTypeIcon(capsule.capsule_type);
    const userInfo = extractUserInfo(capsule);
    const tagCount = capsule.tag_count || 0;
    const isActive = nowPlaying?.id === capsule.id;
    const fileStatus = getFileStatusBadge(capsule);
    const StatusIcon = fileStatus.icon;

    return (
      <div
        className="group relative flex flex-col items-center justify-center z-10 hover:z-40 transition-all duration-300"
        style={{ perspective: '1000px' }}
      >
        {/* 底部发光效果 */}
        <div
          className={`absolute bottom-0 w-32 h-10 blur-[40px] rounded-full transition-all duration-700 ${
            isOpen ? 'opacity-100 blur-[60px]' : isActive ? 'opacity-80 blur-[50px]' : 'opacity-40 group-hover:opacity-80'
          }`}
          style={{ backgroundColor: typeInfo.top }}
        ></div>

        {/* 胶囊主体 */}
        <div
          onClick={() => onClick(capsule.id)}
          className="relative w-36 h-64 cursor-pointer transition-transform duration-500 ease-out hover:scale-105"
        >
          {/* Phase B.3: 文件状态徽章 */}
          <div className={`absolute -top-2 -right-2 z-40 ${fileStatus.bgColor} ${fileStatus.borderColor} border px-2 py-0.5 rounded-full flex items-center gap-1 shadow-lg ${fileStatus.animated ? 'animate-pulse' : ''}`}>
            <StatusIcon size={10} className={fileStatus.textColor} />
            <span className={`text-[8px] font-bold ${fileStatus.textColor}`}>{fileStatus.text}</span>
          </div>

          {/* Phase G: 云同步状态图标 */}
          <div className="absolute -top-2 -left-2 z-40">
            <CloudSyncIcon 
              capsule={capsule} 
              onClick={handleCloudSync}
            />
          </div>

          {/* 上半部分 - The Cap */}
          <div
            className="absolute left-0 right-0 mx-auto top-0 w-full h-[55%] rounded-t-full rounded-b-sm z-30 overflow-hidden transition-all duration-700 cubic-bezier(0.34, 1.56, 0.64, 1)"
            style={{
              backgroundColor: typeInfo.top,
              transform: isOpen ? 'translateY(-80px) rotate(-5deg)' : 'translateY(0)',
              boxShadow: isOpen
                ? `0 20px 40px -10px ${typeInfo.top}40, inset 0 -2px 5px rgba(0,0,0,0.3)`
                : '0 4px 15px rgba(0,0,0,0.5)'
            }}
          >
            {/* 体积阴影 */}
            <div className="absolute inset-0 bg-gradient-to-tr from-black/40 via-transparent to-white/10 pointer-events-none"></div>

            {/* 播放按钮覆盖层 */}
            <div
              className={`absolute inset-0 flex items-center justify-center bg-black/20 backdrop-blur-sm transition-all duration-300 ${
                isActive || 'opacity-0 group-hover:opacity-100'
              }`}
              onClick={(e) => {
                e.stopPropagation();
                handlePlay(capsule);
              }}
            >
              <div className="w-12 h-12 rounded-full border border-white/30 bg-black/30 flex items-center justify-center backdrop-blur-md hover:scale-110 hover:bg-white hover:text-black transition-all text-white shadow-xl">
                {isActive && isPlaying ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" className="ml-1" />}
              </div>
            </div>

            {/* 类型图标和名称 */}
            <div className={`absolute bottom-4 w-full text-center transition-opacity duration-300 ${isActive || 'group-hover:opacity-0'}`}>
              <Icon className="w-6 h-6 text-white/90 mx-auto mb-2 drop-shadow-md" />
              <span className="text-[10px] font-bold text-white/60 tracking-widest uppercase">{capsule.capsule_type}</span>
            </div>
          </div>

          {/* 内部机械结构 - The Core */}
          <div
            className={`absolute left-[-20%] right-[-20%] top-[25%] bottom-[25%] z-20 flex flex-col items-center justify-center gap-3 transition-all duration-500 ${
              isOpen ? 'opacity-100 scale-100 pointer-events-auto' : 'opacity-0 scale-75 pointer-events-none'
            }`}
            onClick={(e) => e.stopPropagation()}
          >
            {/* 连接杆 */}
            <div className="absolute w-[2px] h-[150%] bg-zinc-800 -z-10"></div>

            {/* 操作按钮容器 */}
            <div className="bg-zinc-900/90 backdrop-blur-md border border-zinc-700 p-3 rounded-xl shadow-2xl flex flex-col gap-2 w-full max-w-[180px]">
              {/* 只有胶囊所有者才能编辑 (is_mine=true) */}
              {capsule.is_mine === true && (
                <button
                  onClick={() => onEdit && onEdit(capsule)}
                  className="flex items-center gap-2 w-full px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-300 transition-colors"
                >
                  <Edit size={14} className="text-blue-400" /> <span>编辑</span>
                </button>
              )}
              <SmartActionButton
                status={capsule.asset_status || capsule.cloud_status || 'cloud_only'}
                onClick={() => handleSmartClick(capsule)}
                className="w-full"
              />
              {isAdmin && (
                <button
                  onClick={() => onDelete && onDelete(capsule)}
                  className="flex items-center gap-2 w-full px-3 py-2 rounded-lg bg-red-900/20 hover:bg-red-900/60 text-xs text-red-400 transition-colors"
                >
                  <Trash2 size={14} /> <span>删除</span>
                </button>
              )}
            </div>
          </div>

          {/* 下半部分 - The Body */}
          <div
            className="absolute left-0 right-0 mx-auto bottom-0 w-[92%] h-[48%] rounded-b-full rounded-t-lg z-10 overflow-hidden transition-all duration-700 cubic-bezier(0.34, 1.56, 0.64, 1)"
            style={{
              backgroundColor: typeInfo.bottom,
              transform: isOpen ? 'translateY(90px) rotate(5deg)' : 'translateY(0)',
              boxShadow: isOpen
                ? `0 -20px 40px -10px ${typeInfo.bottom}40, inset 0 2px 5px rgba(255,255,255,0.1)`
                : 'inset 0 10px 20px rgba(0,0,0,0.6)'
            }}
          >
            {/* 体积阴影 */}
            <div className="absolute inset-0 bg-gradient-to-br from-black/50 via-transparent to-black/20 pointer-events-none"></div>

            {/* 播放时的动画效果 */}
            {isActive && isPlaying && (
              <div className="absolute inset-0 flex items-end justify-center gap-1 pb-4 px-6 opacity-30">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div
                    key={i}
                    className="w-2 bg-white animate-pulse"
                    style={{ height: `${Math.random() * 60 + 20}%`, animationDuration: `${Math.random() * 0.5 + 0.2}s` }}
                  ></div>
                ))}
              </div>
            )}

            {/* 使用次数统计 */}
            <div className="absolute top-4 w-full px-4">
              <div className="flex justify-between items-center text-[9px] text-white/50 mb-1">
                <span>USAGE</span>
                <span className="font-mono text-white/90">{capsule.usage_count || 0}</span>
              </div>
              <div className="w-full bg-black/30 h-1 rounded-full overflow-hidden">
                <div className="h-full bg-white/40" style={{ width: `${Math.min(((capsule.usage_count || 0) / 50) * 100, 100)}%` }}></div>
              </div>
            </div>

            {/* 用户名 */}
            {userInfo.hasUser && (
              <div className="absolute bottom-4 left-0 right-0 flex justify-center opacity-40">
                <User size={12} className="text-white" />
                <span className="text-[9px] ml-1 text-white font-mono uppercase">{userInfo.username}</span>
              </div>
            )}
          </div>
        </div>

        {/* 胶囊名称 */}
        <div
          className={`mt-6 text-center transition-all duration-500 ${isOpen ? 'translate-y-24 opacity-100' : 'translate-y-0 opacity-100'}`}
        >
          <h3
            className={`text-sm font-bold tracking-wider font-mono transition-colors ${
              isActive ? 'text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]' : 'text-zinc-100'
            }`}
          >
            {capsule.name || capsule.capsule_type}
          </h3>
          {isOpen && capsule.keywords && (
            <div className="flex flex-wrap justify-center gap-1 mt-2 max-w-[150px]">
              {capsule.keywords.split(',').slice(0, 3).map((k, i) => (
                <span key={i} className="text-[8px] px-1.5 py-0.5 bg-zinc-800 text-zinc-400 rounded border border-zinc-700">
                  {k.trim()}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  // 列表项组件
  const CapsuleListItem = ({ capsule }) => {
    const typeInfo = getTypeColors(capsule.capsule_type);
    const Icon = getTypeIcon(capsule.capsule_type);
    const userInfo = extractUserInfo(capsule);
    const metadata = metadataCache[capsule.id];
    const tags = tagsCache[capsule.id];
    const isActive = nowPlaying?.id === capsule.id;
    const fileStatus = getFileStatusBadge(capsule);
    const StatusIcon = fileStatus.icon;

    // 棱镜名称映射
    const lensNames = {
      texture: '质感',
      source: '源场',
      materiality: '材质',
      temperament: '气质',
      mechanics: '力学'
    };

    // 棱镜颜色映射
    const lensColors = {
      texture: 'text-purple-400 bg-purple-900/20 border-purple-900/30',
      source: 'text-orange-400 bg-orange-900/20 border-orange-900/30',
      materiality: 'text-teal-400 bg-teal-900/20 border-teal-900/30',
      temperament: 'text-pink-400 bg-pink-900/20 border-pink-900/30',
      mechanics: 'text-emerald-400 bg-emerald-900/20 border-emerald-900/30'
    };

    // 安全检查：确保 tags 是有效的对象
    const safeTags = tags && typeof tags === 'object' && tags !== 'LOADING' ? tags : null;
    const hasTags = safeTags && Object.keys(safeTags).length > 0;

    return (
      <div
        className={`group relative flex items-center gap-4 p-4 border rounded-xl transition-all duration-200 backdrop-blur-sm overflow-hidden mb-3 cursor-pointer
        ${isActive
          ? 'bg-zinc-800/80 border-zinc-600 shadow-[0_0_20px_rgba(0,0,0,0.5)]'
          : 'bg-zinc-900/40 border-zinc-800/50 hover:bg-zinc-800/60 hover:border-zinc-700'
        }`}
        onClick={() => handlePlay(capsule)}
      >
        {/* 左侧彩色指示条 */}
        <div className={`absolute left-0 top-0 bottom-0 w-1 transition-all duration-500 ${isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
          style={{ backgroundColor: typeInfo.top }}
        ></div>

        {/* 左侧：图标和名称 */}
        <div className="flex items-center gap-4 min-w-[220px]">
          <div className="relative w-12 h-12 flex items-center justify-center">
            <div className={`absolute inset-0 rounded-lg opacity-20 border border-white/10 transition-all ${isActive ? 'scale-110 opacity-40' : ''}`}
              style={{ backgroundColor: typeInfo.top }}
            ></div>
            {isActive && isPlaying ? (
              <div className="relative z-10 text-white animate-pulse">
                <div className="flex gap-[2px] items-end h-4">
                  <div className="w-1 bg-white h-full animate-[bounce_0.5s_infinite]"></div>
                  <div className="w-1 bg-white h-[60%] animate-[bounce_0.7s_infinite]"></div>
                  <div className="w-1 bg-white h-[80%] animate-[bounce_0.6s_infinite]"></div>
                </div>
              </div>
            ) : (
              <div className={`relative z-10 transition-all ${isActive ? 'text-white' : 'text-zinc-500 group-hover:text-white'}`}>
                {isActive ? <Play size={20} fill="currentColor" /> : <Icon size={20} style={{ color: isActive ? '#fff' : typeInfo.top }} />}
              </div>
            )}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h3 className={`font-bold text-sm tracking-wide transition-colors ${isActive ? 'text-white' : 'text-zinc-200'}`}>
                {capsule.name || capsule.capsule_type}
              </h3>
              {/* Phase B.3: 文件状态徽章 */}
              <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded border ${fileStatus.bgColor} ${fileStatus.borderColor} ${fileStatus.animated ? 'animate-pulse' : ''}`}>
                <StatusIcon size={8} className={fileStatus.textColor} />
                <span className={`text-[8px] font-medium ${fileStatus.textColor}`}>{fileStatus.text}</span>
              </div>
              {/* Phase G: 云同步图标 */}
              <CloudSyncIcon capsule={capsule} onClick={handleCloudSync} />
            </div>
            <div className="flex items-center gap-2 text-[10px] text-zinc-500 mt-1">
              <span className="px-1.5 py-0.5 rounded bg-zinc-950 border border-zinc-800 text-zinc-400 font-mono uppercase">
                {capsule.capsule_type}
              </span>
              {userInfo.hasUser && (
                <span className="flex items-center gap-1">
                  <User size={10} /> {userInfo.username}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* 中间：插件列表和棱镜标签 */}
        <div className="flex-1 hidden md:flex flex-col justify-center gap-2 px-4 border-l border-zinc-800/50">
          {/* 插件列表 */}
          <div className="flex flex-wrap items-center gap-1.5">
            {metadata && metadata.plugins && metadata.plugins.list && metadata.plugins.list.length > 0 ? (
              <>
                <Activity size={12} className="text-zinc-600 mr-1" />
                {metadata.plugins.list.slice(0, 3).map((plugin, i) => (
                  <span key={i} className="text-[10px] px-2 py-0.5 bg-blue-900/10 text-blue-300/80 border border-blue-900/20 rounded-full truncate max-w-[100px]">
                    {plugin.trim()}
                  </span>
                ))}
                {metadata.plugins.list.length > 3 && (
                  <span className="text-[9px] text-zinc-500">+{metadata.plugins.list.length - 3}</span>
                )}
              </>
            ) : (
              <span className="text-[10px] text-zinc-600">No plugins</span>
            )}
          </div>

          {/* 棱镜标签 */}
          {hasTags && (
            <div className="flex flex-wrap items-center gap-1.5">
              {Object.entries(safeTags).map(([lens, lensTags]) => {
                if (!lensTags || !Array.isArray(lensTags) || lensTags.length === 0) return null;

                // 获取棱镜对应的文本颜色（从 lensColors 中提取颜色部分）
                const lensColorClass = lensColors[lens] || 'text-zinc-400';
                // 提取文本颜色类名（例如 "text-purple-400"）
                const textColorClass = lensColorClass.split(' ')[0];

                return (
                  <div key={lens} className="flex items-center gap-1">
                    {lensTags.map((tag, i) => {
                      const tagText = getTagDisplayText(tag);
                      if (!tagText) return null;

                      return (
                        <span key={i} className={`text-[9px] px-1.5 py-0.5 bg-zinc-800 rounded border border-zinc-700 truncate max-w-[80px] ${textColorClass}`}>
                          {tagText}
                        </span>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          )}
          {!hasTags && capsule.keywords && (
            <div className="flex flex-wrap items-center gap-1.5">
              {capsule.keywords.split(',').slice(0, 6).map((keyword, i) => (
                <span
                  key={`${capsule.id}-kw-${i}`}
                  className="text-[9px] px-1.5 py-0.5 bg-zinc-800 rounded border border-zinc-700 text-zinc-300"
                >
                  {keyword.trim()}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* 右侧：统计信息 */}
        <div className="w-32 hidden lg:flex flex-col items-end justify-center text-right text-xs gap-1 border-l border-zinc-800/50 pl-4 h-full">
          <div className="text-zinc-400 font-mono">{(capsule.usage_count || 0).toLocaleString()} <span className="text-zinc-600 text-[9px]">USES</span></div>
          <div className="text-zinc-600 text-[10px]">{formatTime(capsule.created_at)}</div>
        </div>

        {/* 最右侧：操作按钮 */}
        <div className="flex items-center gap-2 pl-4 ml-auto lg:ml-0 border-l border-zinc-800/50 h-full" onClick={(e) => e.stopPropagation()}>
          {/* 只有胶囊所有者才能编辑 (is_mine=true) */}
          {capsule.is_mine === true && (
            <button
              onClick={() => onEdit && onEdit(capsule)}
              className="p-2 rounded-lg bg-zinc-950 hover:bg-zinc-800 text-zinc-400 hover:text-white border border-zinc-800 transition-colors"
              title={t('common.edit')}
            >
              <Edit size={16} />
            </button>
          )}
          <SmartActionButton
            status={capsule.asset_status || capsule.cloud_status || 'cloud_only'}
            onClick={() => handleSmartClick(capsule)}
          />
          {isAdmin && (
            <button
              onClick={() => onDelete && onDelete(capsule)}
              className="p-2 rounded-lg bg-red-900/10 hover:bg-red-900/40 text-red-500/50 hover:text-red-400 border border-transparent hover:border-red-900/50 transition-colors"
              title="删除"
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </div>
    );
  };

  // 渲染列表视图 - 使用 Tailwind CSS
  const renderListView = () => (
    <div className="flex flex-col gap-2 max-w-6xl mx-auto pb-20 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* 列表头 */}
      <div className="grid grid-cols-[240px_1fr_130px_120px] gap-4 px-6 py-2 text-[10px] font-mono text-zinc-600 tracking-widest uppercase border-b border-zinc-800/50 mb-2 hidden md:grid">
        <div>Identity</div>
        <div>Specs & Tags</div>
        <div className="text-right">Statistics</div>
        <div className="pl-4">Actions</div>
      </div>

      {/* 列表项 */}
      {filteredCapsules.map((capsule) => (
        <CapsuleListItem key={capsule.id} capsule={capsule} />
      ))}
    </div>
  );

  // 渲染网络视图 (占位符，后续实现)
  const renderNetworkView = () => (
    <div className="capsules-network-view">
      <div className="network-placeholder">
        <Network size={64} />
        <h2>{t('library.networkViewTitle')}</h2>
        <p>{t('library.networkViewDesc')}</p>
        <p>{t('library.networkViewSub')}</p>
      </div>
    </div>
  );

  return (
    <div className="relative min-h-screen w-full bg-zinc-950 text-zinc-200 font-sans selection:bg-indigo-500/30 overflow-x-hidden pb-32">

      {/* Environment - 背景环境 */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-[-10%] left-[20%] w-[800px] h-[800px] bg-indigo-900/10 blur-[120px] rounded-full"></div>
        <div className="absolute bottom-[-10%] right-[10%] w-[600px] h-[600px] bg-blue-900/10 blur-[100px] rounded-full"></div>
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 brightness-150"></div>
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_at_center,black_40%,transparent_100%)]"></div>
      </div>

      {/* Top Bar - 顶部导航栏 */}
      <div className="sticky top-0 z-50 w-full backdrop-blur-xl border-b border-white/5 bg-black/40 pt-4 pb-6 px-6 lg:px-12 transition-all">
        <div className="max-w-7xl mx-auto flex flex-col gap-6">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="flex items-center gap-3">
              <button
                onClick={onBack}
                className="p-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-white border border-zinc-800 transition-all"
                title={t('library.backToHome')}
              >
                ←
              </button>
              <Box className="text-indigo-500" />
              <h1 className="text-xl font-bold tracking-[0.2em] text-white">SOUND<span className="text-indigo-400">CAPSULE</span>_VAULT</h1>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex bg-zinc-900 p-1 rounded-lg border border-zinc-800">
                <button
                  onClick={() => setViewMode('list')}
                  className={`p-2 rounded-md transition-all ${viewMode === 'list' ? 'bg-zinc-700 text-white shadow-lg' : 'text-zinc-500 hover:text-zinc-300'}`}
                  title="列表视图"
                >
                  <List size={16} />
                </button>
                <button
                  onClick={() => setViewMode('network')}
                  className={`p-2 rounded-md transition-all ${viewMode === 'network' ? 'bg-zinc-700 text-white shadow-lg' : 'text-zinc-500 hover:text-zinc-300'}`}
                  title="关联视图"
                >
                  <Network size={16} />
                </button>
              </div>

              <span className="h-4 w-[1px] bg-zinc-800 mx-2 hidden sm:block"></span>

              <button
                onClick={() => setIsAdmin(!isAdmin)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-[10px] font-bold transition-all ${
                  isAdmin ? 'bg-red-500/20 text-red-400 border border-red-500/50' : 'bg-zinc-800 text-zinc-500 border border-zinc-700'
                }`}
              >
                <User size={12} />
                {isAdmin ? 'ADMIN' : 'USER'}
              </button>

              <span className="h-4 w-[1px] bg-zinc-800 mx-2 hidden sm:block"></span>

              <SyncIndicator />

              <span className="h-4 w-[1px] bg-zinc-800 mx-2 hidden sm:block"></span>

              <UserMenu />
            </div>
          </div>

          <div className="flex flex-col lg:flex-row gap-4 items-center justify-between">
            {/* 搜索框 */}
            <div className="relative w-full lg:max-w-xl group">
              <div className="absolute -inset-0.5 rounded-xl bg-gradient-to-r from-indigo-500/50 to-purple-500/50 opacity-0 group-focus-within:opacity-100 blur transition duration-500"></div>
              <div className="relative flex items-center bg-zinc-900 border border-zinc-700 rounded-xl overflow-hidden shadow-sm">
                <div className="pl-4 text-zinc-500"><Search size={18} /></div>
                <input
                  type="text"
                  placeholder={t('library.searchPlaceholder')}
                  className="w-full bg-transparent border-none outline-none py-3 px-4 text-zinc-200 placeholder-zinc-500 font-mono text-sm"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="pr-4 text-zinc-500 hover:text-zinc-300 transition-colors"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>
            </div>

            {/* 类型过滤按钮 */}
            <div className="flex flex-wrap justify-center gap-2">
              <button
                key="all"
                onClick={() => setSelectedType('all')}
                className={`px-3 py-1.5 rounded-md text-[10px] font-bold tracking-wider border transition-all ${
                  selectedType === 'all'
                    ? 'bg-zinc-100 text-black border-zinc-100 shadow-[0_0_10px_rgba(255,255,255,0.2)]'
                    : 'bg-zinc-900/50 text-zinc-500 border-zinc-800 hover:border-zinc-600 hover:text-zinc-300'
                }`}
              >
                ALL
              </button>
              {capsuleTypes.map(type => (
                <button
                  key={type.id}
                  onClick={() => setSelectedType(type.id)}
                  className={`px-3 py-1.5 rounded-md text-[10px] font-bold tracking-wider border transition-all ${
                    selectedType === type.id
                      ? 'bg-zinc-100 text-black border-zinc-100 shadow-[0_0_10px_rgba(255,255,255,0.2)]'
                      : 'bg-zinc-900/50 text-zinc-500 border-zinc-800 hover:border-zinc-600 hover:text-zinc-300'
                  }`}
                >
                  {i18n.language === 'en' || i18n.language?.startsWith('en') ? (type.name || type.name_cn) : (type.name_cn || type.name)}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content - 主内容区域 */}
      <div className="relative z-10 max-w-[1600px] mx-auto p-4 lg:p-8">
        {filteredCapsules.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-[40vh] text-zinc-600">
            <Search size={48} className="mb-4 opacity-20" />
            <p className="tracking-widest text-sm">{t('library.noCapsulesFound').toUpperCase()}</p>
          </div>
        ) : (
          <>
            {viewMode === 'list' && renderListView()}
            {viewMode === 'network' && renderNetworkView()}
          </>
        )}
      </div>

      {/* Floating Player - 悬浮播放器（已隐藏） */}
      {false && nowPlaying && (
        <div className="fixed bottom-10 left-6 right-6 lg:left-1/2 lg:right-auto lg:-translate-x-1/2 lg:w-[800px] z-50 animate-in slide-in-from-bottom-10 duration-500">
          <div className="relative bg-black/80 backdrop-blur-xl border border-white/10 rounded-2xl p-4 shadow-[0_0_50px_rgba(0,0,0,0.8)] overflow-hidden group">
            {/* 渐变背景 */}
            <div
              className="absolute top-0 left-0 bottom-0 w-full opacity-20 blur-3xl transition-colors duration-1000 pointer-events-none"
              style={{ background: `linear-gradient(90deg, ${getTypeColors(nowPlaying.capsule_type).top} 0%, transparent 100%)` }}
            ></div>

            <div className="relative flex items-center justify-between gap-6">
              {/* 左侧：胶囊信息 */}
              <div className="flex items-center gap-4 min-w-[180px]">
                <div
                  className={`w-12 h-12 rounded-lg flex items-center justify-center border border-white/10 shadow-lg relative overflow-hidden ${isPlaying ? 'animate-pulse' : ''}`}
                  style={{ backgroundColor: getTypeColors(nowPlaying.capsule_type).top }}
                >
                  {(() => {
                    const Icon = getTypeIcon(nowPlaying.capsule_type);
                    return <Icon className="w-6 h-6 text-white relative z-10" />;
                  })()}
                  {isPlaying && <div className="absolute inset-0 bg-white/20 animate-ping"></div>}
                </div>
                <div className="flex flex-col">
                  <span className="text-sm font-bold text-white tracking-wide truncate max-w-[120px]">{nowPlaying.name || t('library.unnamedCapsule')}</span>
                  <span className="text-[10px] text-zinc-400 flex items-center gap-1">
                    {getTypeName(nowPlaying.capsule_type)}
                  </span>
                </div>
              </div>

              {/* 中间：控制按钮和进度条 */}
              <div className="flex-1 flex flex-col gap-2">
                <div className="flex items-center justify-center gap-4">
                  <button
                    onClick={() => setIsPlaying(!isPlaying)}
                    className="w-10 h-10 rounded-full bg-white text-black flex items-center justify-center hover:scale-110 active:scale-95 transition-all shadow-lg shadow-white/20"
                  >
                    {isPlaying ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" className="ml-1" />}
                  </button>
                </div>
                <div className="flex items-center gap-3 text-[10px] font-mono text-zinc-500">
                  <span ref={currentTimeDisplayRef}>0:00</span>
                  <div
                    ref={progressTrackRef}
                    onClick={handleProgressClick}
                    className="relative flex-1 h-1 bg-zinc-800 rounded-full overflow-hidden cursor-pointer group/progress hover:h-1.5 transition-all"
                  >
                    <div
                      ref={progressBarRef}
                      className="absolute top-0 left-0 h-full bg-white/90 rounded-full shadow-[0_0_10px_rgba(255,255,255,0.5)] pointer-events-none"
                      style={{ width: '0%', backgroundColor: getTypeColors(nowPlaying.capsule_type).top, transition: 'none' }}
                    ></div>
                  </div>
                  <span ref={durationDisplayRef} className="text-zinc-300">--:--</span>
                </div>
              </div>

              {/* 右侧：关闭按钮 */}
              <div className="flex items-center gap-4 min-w-[100px] justify-end border-l border-white/5 pl-4">
                <button
                  onClick={() => {
                    setNowPlaying(null);
                    setIsPlaying(false);
                    progressRef.current = 0;
                    setDuration(0);
                    if (progressBarRef.current) progressBarRef.current.style.width = '0%';
                    if (currentTimeDisplayRef.current) currentTimeDisplayRef.current.textContent = '0:00';
                    if (durationDisplayRef.current) durationDisplayRef.current.textContent = '--:--';
                  }}
                  className="p-2 rounded-full hover:bg-white/10 text-zinc-500 hover:text-white transition-colors"
                >
                  <X size={16} />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 底部状态栏 */}
      <div className="fixed bottom-0 w-full h-8 bg-black/90 backdrop-blur border-t border-zinc-800 flex items-center justify-between px-6 z-40 text-[10px] text-zinc-600 font-mono">
        <span className="flex items-center gap-2">
          <span className={`w-1.5 h-1.5 rounded-full ${viewMode === 'network' ? 'bg-pink-500' : 'bg-emerald-500'}`}></span>
          MODE: {viewMode.toUpperCase()}
        </span>
        <div className="flex items-center gap-4">
          <span>{filteredCapsules.length} CAPSULES LOADED</span>
          <span>SYNESTH: V1.0</span>
        </div>
      </div>

      {/* 隐藏的音频元素 */}
      {nowPlaying && (
        <audio
          ref={audioRef}
          src={audioUrl}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onCanPlay={() => {
            // 音频加载完成且可以播放时，如果 shouldAutoPlay 为 true 则自动播放
            if (autoPlayRef.current) {
              audioRef.current?.play().catch(err => {
                if (err.name !== 'AbortError') {
                  console.error('自动播放失败:', err);
                }
              });
              autoPlayRef.current = false;
            }
          }}
        />
      )}

      {/* Phase B.3: 下载进度对话框 */}
      {downloadDialog && (
        <DownloadProgressDialog
          capsuleId={downloadDialog.capsuleId}
          capsuleName={downloadDialog.capsuleName}
          taskStatus={downloadDialog.taskStatus}
          onComplete={handleDownloadComplete}
          onClose={() => setDownloadDialog(null)}
        />
      )}

      {/* JIT: 下载确认弹窗 */}
      {modalCapsule && (
        <DownloadConfirmModal
          capsuleName={modalCapsule.name || modalCapsule.capsule_type}
          onConfirm={handleDownloadConfirm}
          onOfflineOpen={handleOpenRppOnly}
          onClose={() => setModalCapsule(null)}
        />
      )}
    </div>
  );
}

export default CapsuleLibrary;
