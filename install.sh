#!/bin/bash
# =============================================================================
# Codex - 一键安装脚本（引导程序）
# 用法: curl -fsSL https://raw.githubusercontent.com/helocy/codex/main/install.sh | bash
# =============================================================================

set -e

REPO_URL="https://github.com/helocy/codex.git"
REPO_URL_SSH="git@github.com:helocy/codex.git"
INSTALL_DIR="${HOME}/codex"

BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BOLD}"
echo "  ██████╗ ██████╗ ██████╗ ███████╗██╗  ██╗"
echo "  ██╔════╝██╔═══██╗██╔══██╗██╔════╝╚██╗██╔╝"
echo "  ██║     ██║   ██║██║  ██║█████╗   ╚███╔╝ "
echo "  ██║     ██║   ██║██║  ██║██╔══╝   ██╔██╗ "
echo "  ╚██████╗╚██████╔╝██████╔╝███████╗██╔╝ ██╗"
echo "   ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝"
echo -e "${NC}"
echo -e "  ${BOLD}本地 AI 智能知识库 - 安装程序${NC}"
echo ""

# ── 检测操作系统 ───────────────────────────────────────────────────────────────
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS_NAME="macOS"
elif [[ -f /etc/debian_version ]]; then
    OS_NAME="Ubuntu/Debian"
else
    echo -e "${YELLOW}警告: 未识别的操作系统，尝试继续...${NC}"
    OS_NAME="Unknown"
fi
echo -e "  系统: ${BLUE}${OS_NAME}${NC}"
echo -e "  安装目录: ${BLUE}${INSTALL_DIR}${NC}"
echo ""

# ── 确保 git 可用 ──────────────────────────────────────────────────────────────
if ! command -v git &>/dev/null; then
    echo "安装 git..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        xcode-select --install 2>/dev/null || true
        echo "请完成 Xcode 命令行工具安装后重新运行此脚本"
        exit 1
    elif [[ -f /etc/debian_version ]]; then
        sudo apt-get update -qq && sudo apt-get install -y git
    fi
fi

# ── 克隆或更新仓库 ─────────────────────────────────────────────────────────────
if [[ -d "${INSTALL_DIR}/.git" ]]; then
    echo -e "${BLUE}[INFO]${NC}  Codex 目录已存在，拉取最新代码..."
    cd "$INSTALL_DIR"
    git pull --ff-only origin main 2>/dev/null || git pull origin main
else
    echo -e "${BLUE}[INFO]${NC}  克隆 Codex 仓库到 ${INSTALL_DIR} ..."
    # 尝试 HTTPS，如果失败则尝试 SSH
    if ! git clone "$REPO_URL" "$INSTALL_DIR" 2>/dev/null; then
        echo -e "${YELLOW}[WARN]${NC}  HTTPS 克隆失败，尝试使用 SSH..."
        git clone "$REPO_URL_SSH" "$INSTALL_DIR"
    fi
    cd "$INSTALL_DIR"
fi

# ── 运行部署脚本 ───────────────────────────────────────────────────────────────
echo ""
bash deploy.sh
