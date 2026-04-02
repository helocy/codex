#!/bin/bash
# Codex - 一键启动脚本
# 用法: bash start.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "=== 启动 Codex 服务 ==="

# 检查并杀掉已有的后端/前端进程
EXISTING_BACKEND=$(lsof -ti :8001 2>/dev/null)
EXISTING_FRONTEND=$(lsof -ti :5173 2>/dev/null)

if [ -n "$EXISTING_BACKEND" ]; then
    echo "停止已有后端进程 (PID: $EXISTING_BACKEND)..."
    kill $EXISTING_BACKEND 2>/dev/null
fi
if [ -n "$EXISTING_FRONTEND" ]; then
    echo "停止已有前端进程 (PID: $EXISTING_FRONTEND)..."
    kill $EXISTING_FRONTEND 2>/dev/null
fi
[ -n "$EXISTING_BACKEND" ] || [ -n "$EXISTING_FRONTEND" ] && sleep 1

# macOS: 确保 postgresql@15 bin 在 PATH 中
if [[ "$OSTYPE" == "darwin"* ]]; then
    for PG_PATH in /usr/local/opt/postgresql@15/bin /opt/homebrew/opt/postgresql@15/bin; do
        [ -d "$PG_PATH" ] && export PATH="$PG_PATH:$PATH" && break
    done
fi

# 启动后端
echo "启动后端 http://localhost:8001 ..."
cd "$BACKEND_DIR"
if [ -d "venv" ]; then
    source venv/bin/activate
    nohup env NO_PROXY="localhost,127.0.0.1" no_proxy="localhost,127.0.0.1" \
        python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 \
        > /tmp/backend.log 2>&1 &
    BACKEND_PID=$!
    deactivate
else
    nohup env NO_PROXY="localhost,127.0.0.1" no_proxy="localhost,127.0.0.1" \
        python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 \
        > /tmp/backend.log 2>&1 &
    BACKEND_PID=$!
fi
echo "后端 PID: $BACKEND_PID"

sleep 2

# 启动前端
echo "启动前端 http://localhost:5173 ..."
cd "$FRONTEND_DIR"
nohup env NO_PROXY="localhost,127.0.0.1" no_proxy="localhost,127.0.0.1" npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "前端 PID: $FRONTEND_PID"

echo ""
echo "=== 服务已启动 ==="
echo "前端:    http://localhost:5173"
if [[ "$OSTYPE" == "darwin"* ]]; then
    LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "")
else
    LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "")
fi
[ -n "$LAN_IP" ] && echo "局域网:  http://${LAN_IP}:5173"
echo "后端:    http://localhost:8001"
echo "API文档: http://localhost:8001/docs"
echo ""
echo "日志文件:"
echo "  后端: /tmp/backend.log"
echo "  前端: /tmp/frontend.log"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "echo '正在停止...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
wait
