#!/bin/bash

echo "=== Memory 本地开发环境安装指南 ==="
echo ""

# 1. 安装 PostgreSQL
echo "步骤 1: 安装 PostgreSQL"
echo "macOS: brew install postgresql@15 && brew services start postgresql@15"
echo "Ubuntu/Debian: sudo apt install postgresql postgresql-contrib"
echo ""

# 2. 创建数据库
echo "步骤 2: 创建数据库"
echo "  psql -U postgres -c \"CREATE USER memory WITH PASSWORD 'memory123';\""
echo "  psql -U postgres -c \"CREATE DATABASE memory_db OWNER memory;\""
echo ""

# 3. 安装后端依赖
echo "步骤 3: 安装后端依赖"
echo "  cd /Users/yzc/claude/memory/backend"
echo "  python3 -m venv venv"
echo "  source venv/bin/activate"
echo "  pip install -r requirements.txt"
echo ""

# 4. 启动后端
echo "步骤 4: 启动后端（在新终端）"
echo "  cd /Users/yzc/claude/memory/backend"
echo "  source venv/bin/activate"
echo "  python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001"
echo ""

# 5. 启动前端
echo "步骤 5: 启动前端（再开一个新终端）"
echo "  cd /Users/yzc/claude/memory/frontend"
echo "  npm install"
echo "  npm run dev"
echo ""

echo "=== 完成后访问 ==="
echo "前端: http://localhost:5173"
echo "后端: http://localhost:8001/docs"
