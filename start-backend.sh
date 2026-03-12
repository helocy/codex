#!/bin/bash

echo "=== 启动 Memory 后端服务 ==="

cd /Users/yzc/claude/memory/backend

# 激活虚拟环境
source venv/bin/activate

# 启动服务，日志输出到 /tmp
echo "启动 FastAPI 服务在 http://localhost:8001"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
