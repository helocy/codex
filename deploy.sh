#!/bin/bash
# =============================================================================
# Codex - 一键部署脚本
# 支持 macOS (Homebrew) 和 Ubuntu/Debian Linux
# 用法: bash deploy.sh
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
step()    { echo -e "\n${BOLD}━━━ $1 ━━━${NC}"; }

# ── 检测操作系统 ───────────────────────────────────────────────────────────────
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ -f /etc/debian_version ]]; then
        OS="debian"
    elif [[ -f /etc/redhat-release ]]; then
        OS="redhat"
    else
        error "不支持的操作系统，目前支持 macOS / Ubuntu / Debian"
    fi
    info "检测到操作系统: $OS"
}

# ── macOS: 检查 Homebrew ────────────────────────────────────────────────────────
ensure_homebrew() {
    if ! command -v brew &>/dev/null; then
        info "安装 Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        # Apple Silicon 路径修复
        if [[ -f /opt/homebrew/bin/brew ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        fi
    fi
    success "Homebrew 已就绪"
}

# ── 安装系统依赖 ────────────────────────────────────────────────────────────────
install_dependencies() {
    step "安装系统依赖"

    if [[ "$OS" == "macos" ]]; then
        ensure_homebrew

        # PostgreSQL
        if ! command -v psql &>/dev/null; then
            info "安装 PostgreSQL 15..."
            brew install postgresql@15
            brew services start postgresql@15
            # 将 pg 的 bin 加入 PATH（当前 session）
            PG_BIN="$(brew --prefix postgresql@15)/bin"
            export PATH="$PG_BIN:$PATH"
            sleep 3
        else
            success "PostgreSQL 已安装"
        fi

        # Node.js
        if ! command -v node &>/dev/null; then
            info "安装 Node.js..."
            brew install node
        else
            success "Node.js 已安装: $(node -v)"
        fi

        # Python 3
        if ! command -v python3 &>/dev/null; then
            info "安装 Python 3..."
            brew install python@3.11
        else
            success "Python 已安装: $(python3 --version)"
        fi

        # pgvector（从源码编译，兼容 postgresql@15）
        PG_CONFIG="$(brew --prefix postgresql@15)/bin/pg_config"
        PGLIB=$("$PG_CONFIG" --pkglibdir 2>/dev/null)
        if [[ ! -f "${PGLIB}/vector.dylib" ]] && [[ ! -f "${PGLIB}/vector.so" ]]; then
            info "编译安装 pgvector..."
            PGVECTOR_TMP=$(mktemp -d)
            git clone --depth 1 --branch v0.8.0 https://github.com/pgvector/pgvector.git "$PGVECTOR_TMP"
            cd "$PGVECTOR_TMP"
            make PG_CONFIG="$PG_CONFIG" -s
            make install PG_CONFIG="$PG_CONFIG" -s
            cd "$SCRIPT_DIR"
            rm -rf "$PGVECTOR_TMP"
            success "pgvector 安装完成"
        else
            success "pgvector 已安装"
        fi

    elif [[ "$OS" == "debian" ]]; then
        info "更新 apt 索引..."
        sudo apt-get update -qq
        sudo apt-get install -y curl ca-certificates gnupg lsb-release lsof git

        # PostgreSQL 15 + pgvector（via PGDG 官方源，确保 pgvector 可用）
        if ! command -v psql &>/dev/null; then
            info "添加 PostgreSQL 官方源 (PGDG)..."
            curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
                sudo gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg
            echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] \
https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" | \
                sudo tee /etc/apt/sources.list.d/pgdg.list > /dev/null
            sudo apt-get update -qq
            info "安装 PostgreSQL 15 + pgvector..."
            sudo apt-get install -y postgresql-15 postgresql-client-15 postgresql-15-pgvector
            sudo systemctl start postgresql
            sudo systemctl enable postgresql
        else
            success "PostgreSQL 已安装: $(psql --version)"
            PG_VER=$(psql --version 2>/dev/null | grep -oE '[0-9]+' | head -1)
            if ! sudo -u postgres psql -tc "SELECT 1 FROM pg_available_extensions WHERE name='vector'" 2>/dev/null | grep -q 1; then
                info "安装 pgvector (postgresql-${PG_VER}-pgvector)..."
                # 若未添加 PGDG 源则先添加
                if [[ ! -f /etc/apt/sources.list.d/pgdg.list ]]; then
                    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
                        sudo gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg
                    echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] \
https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" | \
                        sudo tee /etc/apt/sources.list.d/pgdg.list > /dev/null
                    sudo apt-get update -qq
                fi
                sudo apt-get install -y postgresql-${PG_VER}-pgvector || \
                    warn "pgvector 安装失败，请参考 https://github.com/pgvector/pgvector"
            else
                success "pgvector 已安装"
            fi
        fi

        # Node.js 20 LTS（via NodeSource）
        if ! command -v node &>/dev/null; then
            info "安装 Node.js 20 LTS..."
            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
            sudo apt-get install -y nodejs
        else
            success "Node.js 已安装: $(node -v)"
        fi

        # Python 3 & venv
        if ! command -v python3 &>/dev/null; then
            sudo apt-get install -y python3 python3-pip python3-venv
        else
            success "Python 已安装: $(python3 --version)"
            python3 -c "import venv" 2>/dev/null || sudo apt-get install -y python3-venv
        fi

        # 构建工具（sentence-transformers 编译需要）
        sudo apt-get install -y build-essential libpq-dev

    elif [[ "$OS" == "redhat" ]]; then
        info "安装 RedHat/CentOS 依赖..."
        sudo dnf install -y postgresql-server postgresql-contrib nodejs npm python3 python3-pip gcc libpq-devel
        sudo postgresql-setup --initdb
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
    fi
}

# ── 配置 PostgreSQL ─────────────────────────────────────────────────────────────
setup_postgres() {
    step "配置 PostgreSQL 数据库"

    # 确保 PostgreSQL 正在运行
    if [[ "$OS" == "macos" ]]; then
        PG_BIN="$(brew --prefix postgresql@15)/bin"
        export PATH="$PG_BIN:$PATH"
        brew services start postgresql@15 2>/dev/null || true
        sleep 2
        PSQL_CMD="psql"
        CREATEUSER_CMD="createuser"
        CREATEDB_CMD="createdb"
        PG_SUPERUSER="$(whoami)"
    else
        PSQL_CMD="sudo -u postgres psql"
        CREATEUSER_CMD="sudo -u postgres createuser"
        CREATEDB_CMD="sudo -u postgres createdb"
        PG_SUPERUSER="postgres"
    fi

    # 创建用户（如果不存在）
    if ! $PSQL_CMD -tAc "SELECT 1 FROM pg_roles WHERE rolname='codex'" 2>/dev/null | grep -q 1; then
        info "创建数据库用户 codex..."
        $PSQL_CMD -c "CREATE USER codex WITH PASSWORD 'codex123';" 2>/dev/null || \
        $PSQL_CMD postgres -c "CREATE USER codex WITH PASSWORD 'codex123';" 2>/dev/null || true
    else
        success "数据库用户 codex 已存在"
    fi

    # 创建数据库（如果不存在）
    if ! $PSQL_CMD -tAc "SELECT 1 FROM pg_database WHERE datname='codex_db'" 2>/dev/null | grep -q 1; then
        info "创建数据库 codex_db..."
        $PSQL_CMD -c "CREATE DATABASE codex_db OWNER codex;" 2>/dev/null || \
        $PSQL_CMD postgres -c "CREATE DATABASE codex_db OWNER codex;" 2>/dev/null || true
    else
        success "数据库 codex_db 已存在"
    fi

    # 授权
    $PSQL_CMD -c "GRANT ALL PRIVILEGES ON DATABASE codex_db TO codex;" 2>/dev/null || \
    $PSQL_CMD postgres -c "GRANT ALL PRIVILEGES ON DATABASE codex_db TO codex;" 2>/dev/null || true

    # 启用 pgvector 扩展
    info "启用 pgvector 扩展..."
    if [[ "$OS" == "macos" ]]; then
        psql codex_db -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true
    else
        sudo -u postgres psql codex_db -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true
    fi

    success "数据库配置完成"
}

# ── 配置后端 Python 环境 ────────────────────────────────────────────────────────
setup_backend() {
    step "配置后端 Python 环境"

    cd "$BACKEND_DIR"

    # 创建虚拟环境
    if [[ ! -d "venv" ]]; then
        info "创建 Python 虚拟环境..."
        python3 -m venv venv
    else
        info "Python 虚拟环境已存在，跳过创建"
    fi

    source venv/bin/activate
    pip install --upgrade pip -q

    info "安装 Python 依赖（首次安装 sentence-transformers 需要下载模型，约 500MB，请耐心等待）..."
    pip install -r requirements.txt -q
    pip install "httpx[socks]" rank-bm25 requests beautifulsoup4 -q

    success "Python 依赖安装完成"
    deactivate
}

# ── 配置环境变量 ────────────────────────────────────────────────────────────────
setup_env() {
    step "配置环境变量"

    ENV_FILE="$BACKEND_DIR/.env"

    if [[ -f "$ENV_FILE" ]]; then
        info ".env 文件已存在，跳过创建（如需修改请直接编辑 backend/.env）"
        return
    fi

    echo ""
    echo -e "${YELLOW}请配置大模型 API（直接回车可跳过，稍后在界面中配置）${NC}"
    echo ""
    echo "支持的大模型服务："
    echo "  1. 豆包 (Doubao) - https://console.volcengine.com/ark"
    echo "  2. 通义千问 (Qwen) - https://dashscope.aliyuncs.com"
    echo "  3. OpenAI - https://platform.openai.com"
    echo "  4. Ollama 本地模型"
    echo "  5. 其他 OpenAI 兼容 API"
    echo ""
    read -p "豆包 API Key（选填，可跳过）: " DOUBAO_KEY
    read -p "豆包模型名称 [doubao-seed-1-6-251015]: " DOUBAO_MODEL_INPUT
    DOUBAO_MODEL="${DOUBAO_MODEL_INPUT:-doubao-seed-1-6-251015}"

    cat > "$ENV_FILE" << EOF
# 数据库配置
POSTGRES_SERVER=localhost
POSTGRES_USER=codex
POSTGRES_PASSWORD=codex123
POSTGRES_DB=codex_db
POSTGRES_PORT=5432

# 文件存储
UPLOAD_DIR=./uploads

# 本地 Embedding 模型（免费，无需配置）
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIM=384

# 豆包大模型（可选）
DOUBAO_API_KEY=${DOUBAO_KEY}
DOUBAO_MODEL=${DOUBAO_MODEL}

# 网络搜索（可选）
# WEB_SEARCH_PROVIDER=duckduckgo
# SERPER_API_KEY=
EOF

    success ".env 文件已创建: $ENV_FILE"
}

# ── 配置前端 ────────────────────────────────────────────────────────────────────
setup_frontend() {
    step "安装前端依赖"
    cd "$FRONTEND_DIR"
    npm install --silent
    success "前端依赖安装完成"
}

# ── 修复 start.sh 使用相对路径 ──────────────────────────────────────────────────
fix_start_script() {
    step "生成启动脚本"

    cat > "$SCRIPT_DIR/start.sh" << 'STARTSCRIPT'
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
    nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload \
        > /tmp/backend.log 2>&1 &
    BACKEND_PID=$!
    deactivate
else
    # 没有 venv，尝试直接使用系统 Python
    nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload \
        > /tmp/backend.log 2>&1 &
    BACKEND_PID=$!
fi
echo "后端 PID: $BACKEND_PID"

sleep 2

# 启动前端
echo "启动前端 http://localhost:5173 ..."
cd "$FRONTEND_DIR"
nohup npm run dev > /tmp/frontend.log 2>&1 &
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
STARTSCRIPT

    chmod +x "$SCRIPT_DIR/start.sh"
    success "start.sh 已生成"
}

# ── 生成 stop.sh ────────────────────────────────────────────────────────────────
fix_stop_script() {
    cat > "$SCRIPT_DIR/stop.sh" << 'STOPSCRIPT'
#!/bin/bash
echo "停止 Codex 服务..."
BACKEND=$(lsof -ti :8001 2>/dev/null)
FRONTEND=$(lsof -ti :5173 2>/dev/null)
[ -n "$BACKEND" ]  && kill $BACKEND  2>/dev/null && echo "后端已停止"
[ -n "$FRONTEND" ] && kill $FRONTEND 2>/dev/null && echo "前端已停止"
echo "完成"
STOPSCRIPT
    chmod +x "$SCRIPT_DIR/stop.sh"
}

# ── 打印完成信息 ────────────────────────────────────────────────────────────────
print_done() {
    echo ""
    echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}${BOLD}║           Codex 部署完成！                          ║${NC}"
    echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BOLD}启动服务：${NC}"
    echo -e "    ${BLUE}bash start.sh${NC}"
    echo ""
    echo -e "  ${BOLD}停止服务：${NC}"
    echo -e "    ${BLUE}bash stop.sh${NC}"
    echo ""
    echo -e "  ${BOLD}访问地址：${NC}"
    echo -e "    前端界面:  ${BLUE}http://localhost:5173${NC}"
    echo -e "    API 文档:  ${BLUE}http://localhost:8001/docs${NC}"
    echo ""
    echo -e "  ${BOLD}首次使用：${NC}"
    echo -e "    1. 在「配置」页配置大模型 API Key"
    echo -e "    2. 在「记忆」页上传 Markdown 文档建立知识库"
    echo -e "    3. 在「对话」页与大模型对话，开启知识库模式"
    echo ""
    if [[ ! -s "$BACKEND_DIR/.env" ]] || ! grep -q "DOUBAO_API_KEY=." "$BACKEND_DIR/.env" 2>/dev/null; then
        echo -e "  ${YELLOW}提示: 尚未配置 API Key，请启动后在「配置」页面配置${NC}"
        echo ""
    fi
}

# ── 主流程 ──────────────────────────────────────────────────────────────────────
main() {
    echo -e "${BOLD}"
    echo "  ███╗   ███╗███████╗███╗   ███╗ ██████╗ ██████╗ ██╗   ██╗"
    echo "  ████╗ ████║██╔════╝████╗ ████║██╔═══██╗██╔══██╗╚██╗ ██╔╝"
    echo "  ██╔████╔██║█████╗  ██╔████╔██║██║   ██║██████╔╝ ╚████╔╝ "
    echo "  ██║╚██╔╝██║██╔══╝  ██║╚██╔╝██║██║   ██║██╔══██╗  ╚██╔╝  "
    echo "  ██║ ╚═╝ ██║███████╗██║ ╚═╝ ██║╚██████╔╝██║  ██║   ██║   "
    echo "  ╚═╝     ╚═╝╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   "
    echo -e "${NC}"
    echo -e "  ${BOLD}本地 AI 智能知识库 - 一键部署脚本${NC}"
    echo "  支持: macOS / Ubuntu / Debian"
    echo ""

    detect_os
    install_dependencies
    setup_postgres
    setup_backend
    setup_env
    setup_frontend
    fix_start_script
    fix_stop_script
    print_done
}

main "$@"
