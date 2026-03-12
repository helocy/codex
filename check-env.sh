#!/bin/bash

echo "=== Codex 本地开发环境检查 ==="
echo ""

# 检查 PostgreSQL
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL 未安装"
    echo ""
    echo "请安装 PostgreSQL："
    echo "  brew install postgresql@15"
    echo "  brew services start postgresql@15"
    echo ""
    exit 1
else
    echo "✅ PostgreSQL 已安装"
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
else
    echo "✅ Python $(python3 --version) 已安装"
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装"
    exit 1
else
    echo "✅ Node.js $(node --version) 已安装"
fi

echo ""
echo "=== 环境检查完成 ==="
