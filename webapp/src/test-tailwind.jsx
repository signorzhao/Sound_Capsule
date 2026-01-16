import React from 'react';

export default function TestTailwind() {
  return (
    <div className="p-8">
      <h1 className="text-4xl font-bold text-blue-500 mb-4">
        Tailwind CSS 测试
      </h1>
      <p className="bg-zinc-900 text-white p-4 rounded-lg border border-white/10">
        如果你能看到这个页面有黑色背景、白色文字和蓝色标题，
        说明 Tailwind CSS 正常工作！
      </p>
      <button className="mt-4 px-6 py-3 bg-gradient-to-r from-indigo-500 to-purple-500 text-white rounded-lg hover:scale-105 transition-transform">
        测试按钮
      </button>
    </div>
  );
}
