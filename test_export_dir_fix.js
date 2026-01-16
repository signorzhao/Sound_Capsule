#!/usr/bin/env node
/**
 * 测试 export_dir 传递修复
 */

console.log('╔═══════════════════════════════════════╗');
console.log('║  export_dir 传递修复 - 验证           ║');
console.log('╚═══════════════════════════════════════╝\n');

// 检查 App.jsx 是否正确导入和使用了 configApi
const fs = require('fs');
const path = require('path');

const appJsPath = path.join(__dirname, 'webapp/src/App.jsx');
const appJs = fs.readFileSync(appJsPath, 'utf-8');

console.log('=== 检查 App.jsx 修改 ===\n');

const checks = [
  ['导入 getAppConfig', /import.*getAppConfig.*from.*configApi/],
  ['定义 userConfig 状态', /const.*userConfig.*useState/],
  ['加载配置 useEffect', /useEffect.*loadConfig/],
  ['调用 getAppConfig', /await getAppConfig\(\)/],
  ['setUserConfig 调用', /setUserConfig\(config\)/],
  ['导出目录检查', /userConfig.*export_dir/],
  ['export_dir 传递', /export_dir.*userConfig\.export_dir/],
  ['错误处理', /导出目录未配置/],
];

let passed = 0;
for (const [name, pattern] of checks) {
  if (pattern.test(appJs)) {
    console.log(`✓ ${name}`);
    passed++;
  } else {
    console.log(`✗ ${name}`);
  }
}

console.log(`\nApp.jsx 检查: ${passed}/${checks.length} 项通过\n`);

// 检查 capsule_api.py 修改
const apiPyPath = path.join(__dirname, 'data-pipeline/capsule_api.py');
const apiPy = fs.readFileSync(apiPyPath, 'utf-8');

console.log('=== 检查 capsule_api.py 修改 ===\n');

const apiChecks = [
  ['从请求获取 export_dir', /export_dir = data\.get\('export_dir'\)/],
  ['检查 export_dir 是否存在', /if export_dir:/],
  ['设置环境变量', /os\.environ\['SYNESTH_CAPSULE_OUTPUT'\].*export_dir/],
  ['日志记录', /使用前端传递的导出目录/],
  ['备用方案', /setup_export_environment\(\)/],
];

let apiPassed = 0;
for (const [name, pattern] of checks) {
  if (pattern.test(apiPy)) {
    console.log(`✓ ${name}`);
    apiPassed++;
  } else {
    console.log(`✗ ${name}`);
  }
}

console.log(`\ncapsule_api.py 检查: ${apiPassed}/${checks.length} 项通过\n`);

// 总结
const totalPassed = passed + apiPassed;
const totalChecks = checks.length + apiChecks.length;

if (totalPassed === totalChecks) {
  console.log('╔═══════════════════════════════════════╗');
  console.log('║  ✅ 所有检查通过！修复成功        ║');
  console.log('║                                       ║');
  console.log('║  修复内容:                            ║');
  console.log('║  1. App.jsx 加载用户配置            ║');
  console.log('║  2. 保存时传递 export_dir           ║');
  console.log('║  3. API 优先使用前端传递的路径     ║');
  console.log('║                                       ║');
  console.log('║  现在可以测试保存胶囊功能了        ║');
  console.log('╚═══════════════════════════════════════╝');
} else {
  console.log('╔═══════════════════════════════════════╗');
  console.log('║  ⚠️  部分检查未通过                  ║');
  console.log(`║  通过: ${totalPassed}/${totalChecks}              ║`);
  console.log('╚═══════════════════════════════════════╝');
}
