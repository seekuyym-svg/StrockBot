#!/bin/bash

# StockBot 环境设置脚本 (Linux/Mac)

echo "============================================================"
echo "🚀 StockBot 环境设置脚本"
echo "============================================================"
echo ""

# 检查conda是否安装
if ! command -v conda &> /dev/null; then
    echo "❌ 错误: 未检测到conda，请先安装Anaconda或Miniconda"
    echo ""
    echo "💡 下载地址: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

echo "✅ 检测到conda"
echo ""

# 询问用户操作
echo "请选择操作:"
echo "1. 创建新环境 (stockbot-py312)"
echo "2. 更新现有环境"
echo "3. 删除环境并重新创建"
echo "4. 仅激活环境"
echo ""
read -p "请输入选项 (1-4): " choice

case $choice in
    1)
        echo ""
        echo "📦 正在创建conda环境 stockbot-py312..."
        conda env create -f environment.yml -n stockbot-py312
        if [ $? -ne 0 ]; then
            echo "❌ 环境创建失败"
            exit 1
        fi
        echo "✅ 环境创建成功！"
        ;;
    2)
        echo ""
        echo "🔄 正在更新conda环境 stockbot-py312..."
        conda env update -f environment.yml -n stockbot-py312 --prune
        if [ $? -ne 0 ]; then
            echo "❌ 环境更新失败"
            exit 1
        fi
        echo "✅ 环境更新成功！"
        ;;
    3)
        echo ""
        echo "⚠️  警告: 这将删除现有环境并重新创建"
        read -p "确认继续? (y/n): " confirm
        if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
            exit 0
        fi
        
        echo "🗑️  正在删除旧环境..."
        conda env remove -n stockbot-py312 -y
        echo "📦 正在重新创建环境..."
        conda env create -f environment.yml -n stockbot-py312
        if [ $? -ne 0 ]; then
            echo "❌ 环境重建失败"
            exit 1
        fi
        echo "✅ 环境重建成功！"
        ;;
    4)
        # 直接激活
        ;;
    *)
        echo "❌ 无效选项"
        exit 1
        ;;
esac

# 激活环境
echo ""
echo "🎯 激活环境 stockbot-py312..."
source $(conda info --base)/etc/profile.d/conda.sh
conda activate stockbot-py312

echo ""
echo "📋 环境信息:"
python --version
echo ""

echo "📁 进入项目目录..."
cd "$(dirname "$0")"

echo ""
echo "📦 检查依赖..."
pip list | grep -E "fastapi|uvicorn|sqlalchemy|pandas|numpy|pyyaml|loguru|pydantic|apscheduler|aiohttp|requests|baostock|akshare"

echo ""
echo "============================================================"
echo "✅ 环境准备完成！"
echo "============================================================"
echo ""
echo "💡 使用提示:"
echo "   - 启动服务: python main.py"
echo "   - 运行测试: python test_etf_system.py"
echo "   - 退出环境: conda deactivate"
echo ""
echo "📖 相关文档:"
echo "   - QUICKSTART.md - 快速开始指南"
echo "   - README.md - 完整文档"
echo ""
