/**
 * k6 压力测试：5002 端口 capsule_api.py 核心流程（不含轻量同步）
 *
 * 覆盖：登录验证、写入本地数据库、上传胶囊、下载胶囊、同步关键词（棱镜）
 * 轻量同步 /api/sync/lightweight 暂不测，等 5002 压完后再单独做轻量化压测。
 * 并发 30 VU，持续 1 分钟
 *
 * 运行前：
 *   1. 启动 API 或确保 5002 服务已运行
 *   2. 设置测试账号（必填）:
 *        export TEST_LOGIN=你的用户名或邮箱
 *        export TEST_PASSWORD=你的密码
 *
 * 运行：
 *   k6 run load-test.js
 *
 * 指定 base URL（压 5002 服务器）：
 *   k6 run -e BASE_URL=http://你的5002地址:5002 load-test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5002';
const TEST_LOGIN = __ENV.TEST_LOGIN || '';
const TEST_PASSWORD = __ENV.TEST_PASSWORD || '';

export const options = {
  vus: 30,
  duration: '1m',
  thresholds: {
    http_req_duration: ['p(95)<10000'],
    http_req_failed: ['rate<0.2'],
  },
};

function login() {
  if (!TEST_LOGIN || !TEST_PASSWORD) {
    console.warn('未设置 TEST_LOGIN/TEST_PASSWORD，将跳过需认证的接口');
    return null;
  }
  const res = http.post(`${BASE_URL}/api/auth/login`, JSON.stringify({
    login: TEST_LOGIN,
    password: TEST_PASSWORD,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
  const ok = check(res, { 'login ok': (r) => r.status === 200 });
  if (!ok) {
    console.warn(`登录失败: ${res.status} ${res.body?.substring(0, 200)}`);
    return null;
  }
  let data;
  try {
    data = res.json();
  } catch (_) {
    return null;
  }
  const token = data?.data?.tokens?.access_token;
  return token || null;
}

export default function () {
  const token = login();

  // 1. 登录验证（已在上方执行，这里仅做健康检查）
  let res = http.get(`${BASE_URL}/api/health`);
  check(res, { 'health ok': (r) => r.status === 200 });

  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  // 2. 写入本地数据库（创建胶囊，无需认证）
  const capsulePayload = JSON.stringify({
    title: `k6-load-${__VU}-${Date.now()}`,
    type: 'magic',
    file_path: '',
  });
  res = http.post(`${BASE_URL}/api/capsules`, capsulePayload, {
    headers: { 'Content-Type': 'application/json' },
  });
  check(res, { 'create capsule ok': (r) => r.status === 201 });

  if (token) {
    // 3. 上传胶囊（可传空 records 仅压测接口）
    res = http.post(
      `${BASE_URL}/api/sync/upload`,
      JSON.stringify({ table: 'capsules', records: [] }),
      { headers }
    );
    check(res, { 'upload ok': (r) => r.status === 200 });

    // 4. 下载胶囊（拉取云端胶囊列表并写本地）
    res = http.get(`${BASE_URL}/api/sync/download?table=capsules`, { headers });
    check(res, { 'download ok': (r) => r.status === 200 });
  }

  // 5. 同步关键词（棱镜）：读棱镜列表
  res = http.get(`${BASE_URL}/api/prisms`);
  check(res, { 'prisms ok': (r) => r.status === 200 });

  sleep(0.3);
}
