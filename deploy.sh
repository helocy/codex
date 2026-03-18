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
        OS_DISPLAY="macOS"
    elif [[ -f /etc/debian_version ]]; then
        OS="debian"
        # 从 /etc/os-release 读取发行版名称（Ubuntu / Debian 等）
        if [[ -f /etc/os-release ]]; then
            OS_DISPLAY=$(. /etc/os-release && echo "${NAME:-Ubuntu/Debian}")
        else
            OS_DISPLAY="Ubuntu/Debian"
        fi
    elif [[ -f /etc/redhat-release ]]; then
        OS="redhat"
        OS_DISPLAY=$(cat /etc/redhat-release | cut -d' ' -f1-2)
    else
        error "不支持的操作系统，目前支持 macOS / Ubuntu / Debian"
    fi
    info "检测到操作系统: $OS_DISPLAY"
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

# ── 辅助：带默认值的 read ────────────────────────────────────────────────────────
ask() {
    # ask <var_name> <prompt> [default]
    local _var="$1" _prompt="$2" _default="$3" _input
    if [[ -n "$_default" ]]; then
        read -p "  $_prompt [${_default}]: " _input
        printf -v "$_var" '%s' "${_input:-$_default}"
    else
        read -p "  $_prompt: " _input
        printf -v "$_var" '%s' "$_input"
    fi
}

ask_secret() {
    # ask_secret <var_name> <prompt>
    local _var="$1" _prompt="$2" _input
    read -s -p "  $_prompt: " _input
    echo ""
    printf -v "$_var" '%s' "$_input"
}

# ── 配置环境变量（交互式向导）────────────────────────────────────────────────────
setup_env() {
    step "配置大模型"

    ENV_FILE="$BACKEND_DIR/.env"

    if [[ -f "$ENV_FILE" ]]; then
        echo ""
        echo -e "  ${YELLOW}检测到已有配置文件 backend/.env${NC}"
        read -p "  是否重新配置？(y/N): " _reconfig
        if [[ "$_reconfig" != "y" && "$_reconfig" != "Y" ]]; then
            info "保留现有配置，跳过配置向导"
            return
        fi
        cp "$ENV_FILE" "${ENV_FILE}.bak"
        info "已备份旧配置到 backend/.env.bak"
    fi

    # ── 公共变量 ──────────────────────────────────────────────────────────────
    LLM_PROVIDER=""
    LLM_API_KEY=""
    LLM_BASE_URL=""
    LLM_MODEL=""
    LLM_PROVIDER_LABEL=""

    echo ""
    echo -e "${BOLD}  ┌─────────────────────────────────────────────────────┐${NC}"
    echo -e "${BOLD}  │  第一步：选择大模型提供商                           │${NC}"
    echo -e "${BOLD}  └─────────────────────────────────────────────────────┘${NC}"
    echo ""
    echo -e "  ${BLUE}1)${NC} 豆包 (Doubao)       — 火山引擎，支持 doubao-seed 系列"
    echo -e "  ${BLUE}2)${NC} 通义千问 (Qwen)     — 阿里云，支持 qwen-plus / qwen-turbo"
    echo -e "  ${BLUE}3)${NC} OpenAI              — GPT-4o、GPT-4-turbo 等"
    echo -e "  ${BLUE}4)${NC} Ollama（本地）       — 无需 API Key，需先安装 Ollama"
    echo -e "  ${BLUE}5)${NC} 其他兼容接口         — 任何 OpenAI 兼容的 API"
    echo -e "  ${BLUE}0)${NC} 跳过，稍后在网页界面配置"
    echo ""
    read -p "  请输入选项 [0-5]: " _choice

    case "$_choice" in
      1)
        LLM_PROVIDER="doubao"
        LLM_PROVIDER_LABEL="豆包 (Doubao)"
        echo ""
        echo -e "  ${YELLOW}→ 获取 API Key: https://console.volcengine.com/ark${NC}"
        echo ""
        ask_secret LLM_API_KEY "API Key"
        ask LLM_MODEL "模型名称" "doubao-seed-1-6-251015"
        LLM_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
        ;;
      2)
        LLM_PROVIDER="qwen"
        LLM_PROVIDER_LABEL="通义千问 (Qwen)"
        echo ""
        echo -e "  ${YELLOW}→ 获取 API Key: https://dashscope.console.aliyun.com${NC}"
        echo ""
        ask_secret LLM_API_KEY "API Key"
        ask LLM_MODEL "模型名称" "qwen-plus"
        LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
        ;;
      3)
        LLM_PROVIDER="openai"
        LLM_PROVIDER_LABEL="OpenAI"
        echo ""
        echo -e "  ${YELLOW}→ 获取 API Key: https://platform.openai.com/api-keys${NC}"
        echo ""
        ask_secret LLM_API_KEY "API Key"
        ask LLM_MODEL "模型名称" "gpt-4o"
        ask LLM_BASE_URL "Base URL（使用代理可修改）" "https://api.openai.com/v1"
        ;;
      4)
        LLM_PROVIDER="ollama"
        LLM_PROVIDER_LABEL="Ollama（本地）"
        echo ""
        echo -e "  ${YELLOW}→ 请确保已安装并启动 Ollama: https://ollama.com${NC}"
        echo ""
        ask LLM_MODEL "模型名称" "llama3"
        ask LLM_BASE_URL "Ollama 地址" "http://localhost:11434/v1"
        LLM_API_KEY="ollama"
        ;;
      5)
        LLM_PROVIDER="custom"
        LLM_PROVIDER_LABEL="自定义兼容接口"
        echo ""
        ask LLM_BASE_URL "Base URL（如 https://api.example.com/v1）" ""
        ask_secret LLM_API_KEY "API Key"
        ask LLM_MODEL "模型名称" ""
        ;;
      *)
        LLM_PROVIDER_LABEL="（跳过，稍后配置）"
        info "已跳过大模型配置，启动后请在「配置」页面设置"
        ;;
    esac

    # ── 第二步：Embedding 模型 ────────────────────────────────────────────────
    echo ""
    echo -e "${BOLD}  ┌─────────────────────────────────────────────────────┐${NC}"
    echo -e "${BOLD}  │  第二步：选择 Embedding 模型                        │${NC}"
    echo -e "${BOLD}  └─────────────────────────────────────────────────────┘${NC}"
    echo ""
    echo -e "  ${BLUE}1)${NC} 本地模型（默认）    — 免费，离线可用，首次下载约 500MB"
    echo -e "  ${BLUE}2)${NC} 豆包 Embedding      — 2048 维，需要豆包 API Key"
    echo -e "  ${BLUE}3)${NC} OpenAI 兼容接口      — 如 text-embedding-3-small"
    echo ""
    read -p "  请输入选项 [1-3，默认 1]: " _emb_choice

    EMBED_MODEL="paraphrase-multilingual-MiniLM-L12-v2"
    EMBED_DIM=384
    EMBED_NOTE="本地免费模型"

    case "$_emb_choice" in
      2)
        EMBED_NOTE="豆包 Embedding"
        ask EMBED_MODEL "Embedding 模型名称" "doubao-embedding-vision-251215"
        EMBED_DIM=2048
        if [[ -z "$LLM_API_KEY" || "$_choice" != "1" ]]; then
            ask_secret EMBED_API_KEY "豆包 API Key（如与上方相同可重复输入）"
        else
            EMBED_API_KEY="$LLM_API_KEY"
            info "复用上方豆包 API Key"
        fi
        ;;
      3)
        EMBED_NOTE="OpenAI 兼容 Embedding"
        ask EMBED_MODEL "模型名称" "text-embedding-3-small"
        ask EMBED_BASE_URL "Base URL" "https://api.openai.com/v1"
        if [[ -z "$LLM_API_KEY" ]]; then
            ask_secret EMBED_API_KEY "API Key"
        else
            EMBED_API_KEY="$LLM_API_KEY"
            info "复用上方 API Key"
        fi
        EMBED_DIM=1536
        ;;
      *)
        EMBED_NOTE="本地免费模型（paraphrase-multilingual-MiniLM-L12-v2）"
        ;;
    esac

    # ── 配置摘要确认 ──────────────────────────────────────────────────────────
    echo ""
    echo -e "${BOLD}  ┌─────────────────────────────────────────────────────┐${NC}"
    echo -e "${BOLD}  │  配置摘要                                           │${NC}"
    echo -e "${BOLD}  └─────────────────────────────────────────────────────┘${NC}"
    echo ""
    echo -e "  大模型:   ${GREEN}${LLM_PROVIDER_LABEL}${NC}"
    [[ -n "$LLM_BASE_URL" ]] && echo -e "  Base URL: ${LLM_BASE_URL}"
    [[ -n "$LLM_MODEL" ]]    && echo -e "  模型:     ${LLM_MODEL}"
    [[ -n "$LLM_API_KEY" ]]  && echo -e "  API Key:  ${LLM_API_KEY:0:6}****"
    echo ""
    echo -e "  Embedding: ${GREEN}${EMBED_NOTE}${NC}"
    echo ""
    read -p "  确认写入配置？(Y/n): " _confirm
    if [[ "$_confirm" == "n" || "$_confirm" == "N" ]]; then
        warn "已取消，请部署完成后手动编辑 backend/.env"
        # 仍需写入最基础的数据库配置
    fi

    # ── 写入 .env ─────────────────────────────────────────────────────────────
    cat > "$ENV_FILE" << EOF
# ── 数据库配置 ──────────────────────────────────
POSTGRES_SERVER=localhost
POSTGRES_USER=codex
POSTGRES_PASSWORD=codex123
POSTGRES_DB=codex_db
POSTGRES_PORT=5432

# ── 文件存储 ────────────────────────────────────
UPLOAD_DIR=./uploads

# ── 大模型配置 ──────────────────────────────────
LLM_PROVIDER=${LLM_PROVIDER}
LLM_API_KEY=${LLM_API_KEY}
LLM_BASE_URL=${LLM_BASE_URL}
LLM_MODEL=${LLM_MODEL}

# ── Embedding 模型 ──────────────────────────────
EMBEDDING_MODEL=${EMBED_MODEL}
EMBEDDING_DIM=${EMBED_DIM}

# ── 网络搜索（可选） ─────────────────────────────
# WEB_SEARCH_PROVIDER=duckduckgo
# SERPER_API_KEY=
EOF

    success ".env 配置已写入: $ENV_FILE"
    echo ""
    echo -e "  ${YELLOW}提示: 可随时编辑 backend/.env 修改配置，或启动后在「配置」页面调整${NC}"
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
