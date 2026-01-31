#!/usr/bin/env bash
# Supabase 官方 Docker 自建部署脚本
# 需先安装 Docker：sudo apt install -y docker.io && sudo usermod -aG docker $USER
set -e
cd /home/sbadmin

echo "[1/6] 克隆 Supabase 仓库..."
if [ ! -d supabase-repo ]; then
  git clone --depth 1 https://github.com/supabase/supabase.git supabase-repo
fi

echo "[2/6] 复制 Docker 配置到 supabase-project..."
rm -rf supabase-project
mkdir -p supabase-project
cp -rf supabase-repo/docker/* supabase-project/
cp supabase-repo/docker/.env.example supabase-project/.env

echo "[3/6] 生成密钥（覆盖 .env 中的占位符）..."
cd supabase-project
if [ -f ./utils/generate-keys.sh ]; then
  sh ./utils/generate-keys.sh
else
  echo "未找到 generate-keys.sh，请手动编辑 .env 并设置 JWT_SECRET、POSTGRES_PASSWORD 等"
  exit 1
fi

echo "[4/6] 拉取镜像..."
docker compose pull

echo "[5/6] 启动服务..."
docker compose up -d

echo "[6/6] 等待服务就绪..."
sleep 15
docker compose ps

echo ""
echo "=== 部署完成 ==="
echo "Studio:  http://$(hostname -I | awk '{print $1}'):3000"
echo "API(Kong): http://$(hostname -I | awk '{print $1}'):8000"
echo "SUPABASE_URL 填: http://<本机IP>:8000"
echo "SUPABASE_SERVICE_ROLE_KEY 见: supabase-project/.env 中的 JWT_SERVICE_ROLE_KEY 或 SERVICE_ROLE_KEY"
echo "后续: 在 Studio SQL Editor 按 执行顺序.md 执行 SQL，并在 Storage 新建私有 bucket: capsule-files"
