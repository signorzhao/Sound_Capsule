import React, { useState, useEffect } from 'react';
import {
  X, Plus, Edit2, Trash2, Save, Settings,
  Sparkles, Flame, Music, Activity, Box,
  Zap, Radio, Headphones, Guitar,
  Piano, Mic, Volume2, Bell,
  Signal, Heart,
  Timer, Clock, Target,
  Star, Sun,
  Moon, Snowflake
} from 'lucide-react';
import { useToast } from './Toast';
import { getApiUrl } from '../utils/apiClient';

// 图标映射
const ICON_MAP = {
  'magic': Sparkles,
  'impact': Flame,
  'atmosphere': Music,
  'texture': Activity
};

// 推荐的图标列表（22个）
const RECOMMENDED_ICONS = [
  { name: 'Sparkles', Icon: Sparkles, category: '特效' },
  { name: 'Flame', Icon: Flame, category: '能量' },
  { name: 'Music', Icon: Music, category: '音乐' },
  { name: 'Activity', Icon: Activity, category: '动态' },
  { name: 'Box', Icon: Box, category: '基础' },
  { name: 'Zap', Icon: Zap, category: '能量' },
  { name: 'Radio', Icon: Radio, category: '设备' },
  { name: 'Headphones', Icon: Headphones, category: '设备' },
  { name: 'Guitar', Icon: Guitar, category: '乐器' },
  { name: 'Piano', Icon: Piano, category: '乐器' },
  { name: 'Mic', Icon: Mic, category: '录音' },
  { name: 'Volume2', Icon: Volume2, category: '音量' },
  { name: 'Bell', Icon: Bell, category: '打击' },
  { name: 'Signal', Icon: Signal, category: '信号' },
  { name: 'Heart', Icon: Heart, category: '动态' },
  { name: 'Timer', Icon: Timer, category: '时间' },
  { name: 'Clock', Icon: Clock, category: '时间' },
  { name: 'Target', Icon: Target, category: '目标' },
  { name: 'Star', Icon: Star, category: '形状' },
  { name: 'Sun', Icon: Sun, category: '自然' },
  { name: 'Moon', Icon: Moon, category: '自然' },
  { name: 'Snowflake', Icon: Snowflake, category: '天气' },
];

// 预设颜色样式（20个）
const COLOR_PRESETS = [
  { name: '紫色魔法', color: '#8B5CF6', gradient: 'linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%)' },
  { name: '红色冲击', color: '#EF4444', gradient: 'linear-gradient(135deg, #EF4444 0%, #F59E0B 100%)' },
  { name: '绿色环境', color: '#10B981', gradient: 'linear-gradient(135deg, #10B981 0%, #06B6D4 100%)' },
  { name: '蓝色纹理', color: '#3B82F6', gradient: 'linear-gradient(135deg, #3B82F6 0%, #6366F1 100%)' },
  { name: '粉红梦幻', color: '#EC4899', gradient: 'linear-gradient(135deg, #EC4899 0%, #8B5CF6 100%)' },
  { name: '橙色温暖', color: '#F97316', gradient: 'linear-gradient(135deg, #F97316 0%, #EF4444 100%)' },
  { name: '青色清新', color: '#06B6D4', gradient: 'linear-gradient(135deg, #06B6D4 0%, #3B82F6 100%)' },
  { name: '金色华丽', color: '#F59E0B', gradient: 'linear-gradient(135deg, #F59E0B 0%, #EF4444 100%)' },
  { name: '紫罗兰', color: '#7C3AED', gradient: 'linear-gradient(135deg, #7C3AED 0%, #DB2777 100%)' },
  { name: '玫瑰红', color: '#F43F5E', gradient: 'linear-gradient(135deg, #F43F5E 0%, #EC4899 100%)' },
  { name: '天空蓝', color: '#0EA5E9', gradient: 'linear-gradient(135deg, #0EA5E9 0%, #06B6D4 100%)' },
  { name: '薄荷绿', color: '#14B8A6', gradient: 'linear-gradient(135deg, #14B8A6 0%, #10B981 100%)' },
  { name: '深紫', color: '#6366F1', gradient: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)' },
  { name: '珊瑚色', color: '#FB7185', gradient: 'linear-gradient(135deg, #FB7185 0%, #F43F5E 100%)' },
  { name: '琥珀色', color: '#FBBF24', gradient: 'linear-gradient(135deg, #FBBF24 0%, #F97316 100%)' },
  { name: '靛蓝', color: '#4F46E5', gradient: 'linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%)' },
  { name: '祖母绿', color: '#059669', gradient: 'linear-gradient(135deg, #059669 0%, #10B981 100%)' },
  { name: '深红', color: '#DC2626', gradient: 'linear-gradient(135deg, #DC2626 0%, #EA580C 100%)' },
  { name: '深橙', color: '#EA580C', gradient: 'linear-gradient(135deg, #EA580C 0%, #DC2626 100%)' },
  { name: '蓝宝石', color: '#2563EB', gradient: 'linear-gradient(135deg, #2563EB 0%, #4F46E5 100%)' },
];

/**
 * 胶囊类型管理组件
 *
 * 功能：
 * - 查看、编辑、删除胶囊类型
 * - 创建新胶囊类型
 * - 为每个类型配置优先棱镜
 */

function CapsuleTypeManager({ onClose }) {
  const toast = useToast();
  const [capsuleTypes, setCapsuleTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingType, setEditingType] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [showIconPicker, setShowIconPicker] = useState(false);
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [availableLenses, setAvailableLenses] = useState([]);  // 新增：可用棱镜列表

  // 加载可用棱镜列表
  const loadAvailableLenses = async () => {
    try {
      const response = await fetch('http://localhost:5001/api/config');
      const config = await response.json();

      // 转换为选项格式
      const lensOptions = Object.keys(config).map(lensId => ({
        value: lensId,
        label: config[lensId].name || lensId,
        id: lensId
      }));

      setAvailableLenses(lensOptions);
    } catch (error) {
      console.error('加载棱镜列表失败:', error);
      // 使用默认列表作为后备
      setAvailableLenses([
        { value: 'texture', label: '纹理', id: 'texture' },
        { value: 'source', label: '来源', id: 'source' },
        { value: 'materiality', label: '物质性', id: 'materiality' },
        { value: 'temperament', label: '性格', id: 'temperament' },
        { value: 'mechanics', label: '力学', id: 'mechanics' }
      ]);
    }
  };

  // 加载胶囊类型
  const loadCapsuleTypes = async () => {
    try {
      setLoading(true);
      const response = await fetch(getApiUrl('/api/capsule-types'));
      const data = await response.json();

      if (data.success) {
        setCapsuleTypes(data.types);
      } else {
        toast.error('加载胶囊类型失败');
      }
    } catch (error) {
      console.error('加载胶囊类型失败:', error);
      toast.error('加载胶囊类型失败: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCapsuleTypes();
    loadAvailableLenses();  // 加载可用棱镜列表
  }, []);

  // 创建新类型
  const handleCreate = () => {
    setIsCreating(true);
    setEditingType({
      id: '',
      name: '',
      name_cn: '',
      description: '',
      icon: 'Box',
      color: '#8B5CF6',
      gradient: 'linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%)',
      examples: [],
      priority_lens: 'texture',
      sort_order: capsuleTypes.length + 1
    });
  };

  // 编辑类型
  const handleEdit = (type) => {
    setIsCreating(false);
    setEditingType({ ...type });
  };

  // 保存类型
  const handleSave = async () => {
    try {
      // 验证必填字段
      if (!editingType.id || !editingType.name || !editingType.name_cn) {
        toast.error('请填写所有必填字段');
        return;
      }

      // 验证ID格式
      const idRegex = /^[a-zA-Z0-9_]+$/;
      if (!idRegex.test(editingType.id)) {
        toast.error('ID只能包含字母、数字和下划线');
        return;
      }

      const url = isCreating
        ? getApiUrl('/api/capsule-types')
        : getApiUrl(`/api/capsule-types/${editingType.id}`);

      const method = isCreating ? 'POST' : 'PUT';

      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editingType)
      });

      const data = await response.json();

      if (data.success) {
        toast.success(isCreating ? '创建成功' : '保存成功');
        setEditingType(null);
        setIsCreating(false);
        loadCapsuleTypes();
      } else {
        toast.error(data.error || '保存失败');
      }
    } catch (error) {
      console.error('保存失败:', error);
      toast.error('保存失败: ' + error.message);
    }
  };

  // 删除类型
  const handleDelete = async (typeId) => {
    if (!confirm('确定要删除此胶囊类型吗？')) {
      return;
    }

    try {
      const response = await fetch(getApiUrl(`/api/capsule-types/${typeId}`), {
        method: 'DELETE'
      });

      const data = await response.json();

      if (data.success) {
        toast.success('删除成功');
        loadCapsuleTypes();
      } else {
        toast.error(data.error || '删除失败');
      }
    } catch (error) {
      console.error('删除失败:', error);
      toast.error('删除失败: ' + error.message);
    }
  };

  // 添加示例
  const addExample = () => {
    setEditingType(prev => ({
      ...prev,
      examples: [...(prev.examples || []), '']
    }));
  };

  // 更新示例
  const updateExample = (index, value) => {
    setEditingType(prev => ({
      ...prev,
      examples: prev.examples.map((ex, i) => i === index ? value : ex)
    }));
  };

  // 删除示例
  const removeExample = (index) => {
    setEditingType(prev => ({
      ...prev,
      examples: prev.examples.filter((_, i) => i !== index)
    }));
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-zinc-950/95 backdrop-blur-xl">
        <div className="text-zinc-400">加载中...</div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[2000] overflow-y-auto">
      {/* 背景 */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[20%] w-[800px] h-[800px] bg-indigo-900/10 blur-[120px] rounded-full"></div>
        <div className="absolute bottom-[-10%] right-[10%] w-[600px] h-[600px] bg-blue-900/10 blur-[100px] rounded-full"></div>
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 brightness-150"></div>
      </div>

      {/* 主内容 */}
      <div className="relative min-h-screen bg-zinc-950">
        {/* 头部 */}
        <div className="sticky top-0 z-50 backdrop-blur-xl border-b border-white/5 bg-black/40 pt-4 pb-6 px-6 lg:px-12">
          <div className="max-w-7xl mx-auto flex justify-between items-center">
            <div className="flex items-center gap-3">
              <Settings className="text-indigo-500 w-6 h-6" />
              <h1 className="text-xl font-bold tracking-[0.2em] text-white">
                胶囊<span className="text-indigo-400">类型</span>管理
              </h1>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={handleCreate}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-bold text-sm transition-all shadow-lg shadow-indigo-900/20"
              >
                <Plus size={16} />
                新建类型
              </button>
              <button
                onClick={onClose}
                className="p-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-white border border-zinc-800 transition-all"
              >
                <X size={20} />
              </button>
            </div>
          </div>
        </div>

        {/* 内容区 */}
        <div className="max-w-7xl mx-auto px-6 lg:px-12 py-8">
          {/* 编辑器 */}
          {editingType && (
            <div className="mb-8 bg-zinc-900/40 backdrop-blur-sm border border-white/5 rounded-xl p-6 animate-in fade-in slide-in-from-top-4 duration-300">
              <div className="flex justify-between items-center mb-6 pb-4 border-b border-zinc-800">
                <h2 className="text-lg font-bold text-white">
                  {isCreating ? '新建胶囊类型' : '编辑胶囊类型'}
                </h2>
                <div className="flex gap-3">
                  <button
                    onClick={handleSave}
                    className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-bold text-sm transition-all shadow-lg"
                  >
                    <Save size={16} />
                    保存
                  </button>
                  <button
                    onClick={() => setEditingType(null)}
                    className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg font-bold text-sm transition-all"
                  >
                    取消
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 左侧：表单 */}
                <div className="space-y-6">
                  {/* 基本信息 */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-widest">基本信息</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1.5">ID *</label>
                        <input
                          type="text"
                          value={editingType.id}
                          onChange={(e) => setEditingType(prev => ({ ...prev, id: e.target.value }))}
                          disabled={!isCreating}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500 disabled:opacity-50"
                          placeholder="例如: magic"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1.5">英文名 *</label>
                        <input
                          type="text"
                          value={editingType.name}
                          onChange={(e) => setEditingType(prev => ({ ...prev, name: e.target.value }))}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                          placeholder="例如: MAGIC"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1.5">中文名 *</label>
                        <input
                          type="text"
                          value={editingType.name_cn}
                          onChange={(e) => setEditingType(prev => ({ ...prev, name_cn: e.target.value }))}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                          placeholder="例如: 魔法"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1.5">图标</label>
                        <button
                          onClick={() => setShowIconPicker(!showIconPicker)}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500 flex items-center justify-between hover:border-zinc-700 transition-all"
                        >
                          <span className="flex items-center gap-2">
                            {(() => {
                              const iconItem = RECOMMENDED_ICONS.find(item => item.name === editingType.icon);
                              const IconComponent = iconItem ? iconItem.Icon : Box;
                              return <IconComponent size={16} />;
                            })()}
                            {editingType.icon}
                          </span>
                          <span className="text-zinc-500">选择</span>
                        </button>
                        {showIconPicker && (
                          <div className="mt-2 p-4 bg-zinc-900 border border-zinc-800 rounded-xl max-h-64 overflow-y-auto">
                            <div className="grid grid-cols-8 gap-2">
                              {RECOMMENDED_ICONS.map((item) => {
                                const IconComponent = item.Icon;
                                return (
                                  <button
                                    key={item.name}
                                    onClick={() => {
                                      setEditingType(prev => ({ ...prev, icon: item.name }));
                                      setShowIconPicker(false);
                                    }}
                                    className={`p-3 rounded-lg transition-all ${
                                      editingType.icon === item.name
                                        ? 'bg-indigo-600 text-white'
                                        : 'bg-zinc-950 text-zinc-400 hover:bg-zinc-800 hover:text-white'
                                    }`}
                                    title={item.name}
                                  >
                                    <IconComponent size={20} />
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1.5">颜色样式</label>
                        <button
                          onClick={() => setShowColorPicker(!showColorPicker)}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500 flex items-center justify-between hover:border-zinc-700 transition-all"
                        >
                          <span className="flex items-center gap-2">
                            <span
                              className="w-4 h-4 rounded"
                              style={{ background: editingType.gradient }}
                            ></span>
                            {COLOR_PRESETS.find(p => p.color === editingType.color)?.name || '自定义'}
                          </span>
                          <span className="text-zinc-500">选择</span>
                        </button>
                        {showColorPicker && (
                          <div className="mt-2 p-4 bg-zinc-900 border border-zinc-800 rounded-xl max-h-64 overflow-y-auto">
                            <div className="grid grid-cols-4 gap-2">
                              {COLOR_PRESETS.map((preset) => (
                                <button
                                  key={preset.name}
                                  onClick={() => {
                                    setEditingType(prev => ({
                                      ...prev,
                                      color: preset.color,
                                      gradient: preset.gradient
                                    }));
                                    setShowColorPicker(false);
                                  }}
                                  className={`p-3 rounded-lg transition-all ${
                                    editingType.color === preset.color
                                      ? 'ring-2 ring-indigo-500'
                                      : 'hover:ring-2 hover:ring-zinc-700'
                                  }`}
                                  title={preset.name}
                                >
                                  <div
                                    className="w-full h-12 rounded-lg"
                                    style={{ background: preset.gradient }}
                                  ></div>
                                  <div className="text-xs text-zinc-400 mt-1">{preset.name}</div>
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1.5">优先棱镜</label>
                        <select
                          value={editingType.priority_lens}
                          onChange={(e) => setEditingType(prev => ({ ...prev, priority_lens: e.target.value }))}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                        >
                          {availableLenses.map(lens => (
                            <option key={lens.value} value={lens.value}>
                              {lens.label}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1.5">排序</label>
                        <input
                          type="number"
                          value={editingType.sort_order}
                          onChange={(e) => setEditingType(prev => ({ ...prev, sort_order: parseInt(e.target.value) }))}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs text-zinc-500 mb-1.5">描述</label>
                      <textarea
                        value={editingType.description}
                        onChange={(e) => setEditingType(prev => ({ ...prev, description: e.target.value }))}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500 resize-none"
                        placeholder="简要描述此胶囊类型的用途"
                        rows={3}
                      />
                    </div>
                  </div>

                  {/* 示例标签 */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-widest">示例标签</h3>
                    <div className="space-y-2">
                      {editingType.examples?.map((example, index) => (
                        <div key={index} className="flex gap-2">
                          <input
                            type="text"
                            value={example}
                            onChange={(e) => updateExample(index, e.target.value)}
                            className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                            placeholder="例如: 粒子合成"
                          />
                          <button
                            onClick={() => removeExample(index)}
                            className="p-2.5 rounded-lg bg-red-900/10 hover:bg-red-900/40 text-red-500/50 hover:text-red-400 border border-transparent hover:border-red-900/50 transition-all"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      ))}
                      <button
                        onClick={addExample}
                        className="flex items-center justify-center gap-2 w-full py-2.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-white rounded-lg font-bold text-sm transition-all border border-zinc-800"
                      >
                        <Plus size={16} />
                        添加示例
                      </button>
                    </div>
                  </div>
                </div>

                {/* 右侧：预览 */}
                <div className="space-y-4">
                  <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-widest">预览</h3>
                  <div
                    className="relative bg-gradient-to-br from-zinc-900 to-zinc-950 border border-white/5 rounded-2xl p-12 text-center overflow-hidden"
                  >
                    {/* 渐变背景 */}
                    <div className="absolute inset-0 opacity-20" style={{ background: editingType.gradient }}></div>

                    {/* 内容 */}
                    <div className="relative">
                      <div style={{ filter: `drop-shadow(0 0 30px ${editingType.color})` }}>
                        {(() => {
                          const iconItem = RECOMMENDED_ICONS.find(item => item.name === editingType.icon);
                          const IconComponent = iconItem ? iconItem.Icon : Box;
                          return <IconComponent size={64} />;
                        })()}
                      </div>
                      <div className="text-2xl font-bold text-white mb-2">
                        {editingType.name_cn || '类型名称'}
                      </div>
                      <div className="text-sm text-zinc-400 mb-6">
                        {editingType.name || 'NAME'}
                      </div>
                      <div className="text-sm text-zinc-500 mb-6">
                        {editingType.description || '描述文字'}
                      </div>
                      <div className="flex flex-wrap gap-2 justify-center">
                        {editingType.examples?.filter(e => e).map((ex, i) => (
                          <span
                            key={i}
                            className="px-3 py-1.5 bg-zinc-800 text-zinc-300 rounded-full text-xs border border-zinc-700"
                          >
                            {ex}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 类型列表 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {capsuleTypes.map((type) => (
              <div
                key={type.id}
                className="group relative bg-zinc-900/40 backdrop-blur-sm border border-white/5 rounded-xl p-5 hover:border-zinc-700 transition-all"
              >
                {/* 类型预览 */}
                <div className="flex items-start gap-4 mb-4">
                  <div
                    className="w-16 h-16 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{ background: type.gradient }}
                  >
                    {(() => {
                      const iconItem = RECOMMENDED_ICONS.find(item => item.name === type.icon);
                      const IconComponent = iconItem ? iconItem.Icon : Box;
                      return <IconComponent size={32} style={{ filter: `drop-shadow(0 0 10px ${type.color})` }} />;
                    })()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-bold text-white mb-1 truncate">
                      {type.name_cn}
                    </h3>
                    <p className="text-xs text-zinc-500 mb-1">{type.name}</p>
                    <p className="text-sm text-zinc-400 line-clamp-2">
                      {type.description}
                    </p>
                  </div>
                </div>

                {/* 元数据 */}
                <div className="flex flex-wrap gap-2 mb-4">
                  <span className="px-2 py-1 bg-zinc-950 text-zinc-500 rounded text-[10px] font-mono border border-zinc-800">
                    ID: {type.id}
                  </span>
                  <span className="px-2 py-1 bg-zinc-950 text-zinc-500 rounded text-[10px] font-mono border border-zinc-800">
                    棱镜: {type.priority_lens}
                  </span>
                  <span className="px-2 py-1 bg-zinc-950 text-zinc-500 rounded text-[10px] font-mono border border-zinc-800">
                    排序: {type.sort_order}
                  </span>
                </div>

                {/* 示例标签 */}
                {type.examples?.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-4">
                    {type.examples.filter(e => e).map((ex, i) => (
                      <span
                        key={i}
                        className="px-2 py-1 bg-zinc-950 text-zinc-400 rounded text-[10px] border border-zinc-800"
                      >
                        {ex}
                      </span>
                    ))}
                  </div>
                )}

                {/* 操作按钮 */}
                <div className="flex gap-2 pt-4 border-t border-zinc-800/50">
                  <button
                    onClick={() => handleEdit(type)}
                    className="flex-1 flex items-center justify-center gap-2 py-2 bg-zinc-950 hover:bg-zinc-800 text-zinc-400 hover:text-white rounded-lg font-bold text-xs transition-all border border-zinc-800"
                  >
                    <Edit2 size={14} />
                    编辑
                  </button>
                  <button
                    onClick={() => handleDelete(type.id)}
                    className="p-2 bg-red-900/10 hover:bg-red-900/40 text-red-500/50 hover:text-red-400 rounded-lg border border-transparent hover:border-red-900/50 transition-all"
                    title="删除"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default CapsuleTypeManager;
