#!/bin/bash
# Memory 项目停止脚本

echo "🛑 停止 Memory 项目..."
echo ""

# 停止后端
BACKEND=$(lsof -ti :8001 2>/dev/null)
if [ -n "$BACKEND" ]; then
    kill $BACKEND 2>/dev/null
    echo "✅ 后端服务已停止 (PID: $BACKEND)"
else
    echo "⚠️  没有运行的后端服务"
fi

# 停止前端
FRONTEND=$(lsof -ti :5173 2>/dev/null)
if [ -n "$FRONTEND" ]; then
    kill $FRONTEND 2>/dev/null
    echo "✅ 前端服务已停止 (PID: $FRONTEND)"
else
    echo "⚠️  没有运行的前端服务"
fi

# 清理可能残留的进程
echo ""
echo "🧹 检查残留进程..."
pkill -f "uvicorn app.main:app" 2>/dev/null && echo "✅ 已清理 uvicorn 进程" || true
pkill -f "vite" 2>/dev/null && echo "✅ 已清理 vite 进程" || true

echo ""
echo "✨ Memory 项目已停止"
