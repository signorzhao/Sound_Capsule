#!/bin/bash

# GitHub Actions 测试结果快速查看脚本
# 使用方法: ./check_test_results.sh

echo "=========================================="
echo "GitHub Actions 测试结果查看器"
echo "=========================================="
echo ""

# 检查是否安装了 GitHub CLI
if ! command -v gh &> /dev/null; then
    echo "❌ 未安装 GitHub CLI"
    echo ""
    echo "请先安装:"
    echo "  brew install gh"
    echo "  gh auth login"
    echo ""
    echo "或者直接在网页查看:"
    echo "  https://github.com/signorzhao/Sound_Capsule/actions"
    exit 1
fi

# 检查是否已登录
if ! gh auth status &> /dev/null; then
    echo "❌ 未登录 GitHub CLI"
    echo "请运行: gh auth login"
    exit 1
fi

echo "📋 最近的测试运行:"
echo ""

# 获取最近的运行
gh run list --workflow="Build and Test Windows" --limit 5

echo ""
echo "=========================================="
echo "选择要查看的运行:"
echo "=========================================="
echo ""
echo "1. 查看最新运行的日志"
echo "2. 查看最新运行的详细输出"
echo "3. 下载最新运行的测试结果"
echo "4. 查看失败运行的错误"
echo "5. 打开网页查看"
echo ""
read -p "请选择 (1-5): " choice

case $choice in
    1)
        echo ""
        echo "📄 最新运行的日志:"
        echo "=========================================="
        gh run view --log --workflow="Build and Test Windows" | head -100
        ;;
    2)
        echo ""
        echo "📊 最新运行的详细输出:"
        echo "=========================================="
        gh run view --log --workflow="Build and Test Windows"
        ;;
    3)
        echo ""
        echo "📥 下载测试结果..."
        gh run download --workflow="Build and Test Windows"
        echo ""
        echo "✅ 下载完成！文件在 artifacts/ 目录"
        echo ""
        echo "查看日志:"
        echo "  cat artifacts/*/export_debug.log"
        ;;
    4)
        echo ""
        echo "❌ 最近的失败运行:"
        gh run list --workflow="Build and Test Windows" --status failure --limit 3
        echo ""
        read -p "输入运行 ID 查看详情 (或按回车查看最新的): " run_id
        if [ -z "$run_id" ]; then
            gh run view --log --workflow="Build and Test Windows" | grep -i "error\|失败\|异常\|✗" -A 10
        else
            gh run view $run_id --log | grep -i "error\|失败\|异常\|✗" -A 10
        fi
        ;;
    5)
        echo ""
        echo "🌐 在浏览器中打开..."
        open "https://github.com/signorzhao/Sound_Capsule/actions/workflows/build-and-test-windows.yml"
        ;;
    *)
        echo "无效选择"
        ;;
esac
