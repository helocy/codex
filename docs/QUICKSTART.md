# Codex 快速启动指南

## 一、在新电脑上部署

### 前置要求

| 项目 | 要求 |
|------|------|
| 操作系统 | macOS 12+ / Ubuntu 20.04+ / Debian 11+ |
| 内存 | ≥ 4GB（本地 embedding 模型约占 500MB）|
| 磁盘 | ≥ 10GB（Python 依赖 + 模型缓存 + 向量数据）|
| 网络 | 首次部署需要下载依赖和模型 |

### 一键部署

```bash
# 1. 获取代码
git clone <repo-url> codex
cd codex

# 2. 执行部署脚本（自动安装所有依赖）
bash deploy.sh
```

脚本会自动完成以下所有步骤：
- 安装 PostgreSQL、Node.js、Python（如未安装）
- 创建数据库用户和数据库
- 安装 Python 虚拟环境和所有依赖包
- 安装前端 npm 依赖
- 生成 `.env` 配置文件（可输入 API Key，也可跳过）
- 生成 `start.sh` / `stop.sh` 启动脚本

> 首次部署约需 5-15 分钟（主要是下载 embedding 模型 ~500MB）

### 启动服务

```bash
bash start.sh
```

访问：
- 前端界面：http://localhost:5173
- API 文档：http://localhost:8001/docs

### 停止服务

```bash
bash stop.sh
# 或直接 Ctrl+C（如果 start.sh 在前台运行）
```

---

## 二、配置大模型

### 在界面中配置

打开 http://localhost:5173，点击顶部「⚙️ 设置」标签，填写：

| 字段 | 说明 |
|------|------|
| API Base URL | 大模型服务的接口地址 |
| API Key | 鉴权密钥 |
| 模型名称 | 要使用的模型 ID |

点击「保存配置」即生效，无需重启服务。

### 各服务配置参考

**豆包 (Doubao)**
```
Base URL:  https://ark.cn-beijing.volces.com/api/v3
API Key:   <在 https://console.volcengine.com/ark 获取>
模型名称:  doubao-seed-1-6-251015
```

**通义千问 (Qwen)**
```
Base URL:  https://dashscope.aliyuncs.com/compatible-mode/v1
API Key:   <在 https://dashscope.aliyuncs.com 获取>
模型名称:  qwen-plus
```

**OpenAI**
```
Base URL:  https://api.openai.com/v1
API Key:   sk-...
模型名称:  gpt-4o
```

**Ollama（本地模型，无需 API Key）**
```
Base URL:  http://localhost:11434/v1
API Key:   ollama
模型名称:  llama3（或已下载的任意模型）
```

---

## 三、配置 Embedding 模型

Codex 支持三种 embedding 模型：

| 提供商 | 模型名称 | 说明 |
|--------|----------|------|
| 本地 (sentence-transformers) | paraphrase-multilingual-MiniLM-L12-v2 | 免费，无需 API Key，默认使用 |
| 豆包 Embedding | doubao-embedding-vision-251215 | 需要豆包 API Key，向量维度 256 |
| 云端 API (OpenAI 兼容) | text-embedding-3-small | 需要 API Key |

### 配置步骤

1. 点击「⚙️ 设置」标签
2. 在「嵌入模型配置」区域选择提供商
3. 填写模型名称和 API Key（本地模型不需要）
4. 点击「保存配置」

> ⚠️ **重要**：更换 embedding 模型后，需要在「管理」页重置知识库并重新上传文档，因为不同模型的向量维度不兼容。

---

## 四、建立知识库

### 上传单个文件

1. 点击「💾 记忆」标签
2. 在「单个文件」区域点击选择文件
3. 等待上传和向量化完成

### 批量上传目录

1. 点击「💾 记忆」标签
2. 在「批量上传目录」区域点击选择文件夹
3. 系统会自动扫描目录下所有 .md 和 .pdf 文件
4. 进度日志实时更新，上传完成后保留日志

### 支持的文件格式

| 格式 | 分块策略 |
|------|----------|
| `.md` | Markdown 感知分块（按 #/##/### 标题切分，保留语义单元）|
| `.pdf` | 按页分块（每页一个 chunk）|
| `.docx` / `.doc` | 字符级分块 |
| `.txt` | 字符级分块 |

---

## 五、使用知识库对话

1. 点击「💬 对话」标签（默认显示）
2. 勾选底部的选项：
   - **知识库**：使用你上传的文档回答（默认勾选）
   - **原始文档**：查找并使用完整的原始文档内容（默认勾选）
   - **联网搜索**：从互联网搜索相关信息
3. 输入问题，按 Enter 或点击「发送」
4. 回答下方会显示引用的来源

**选项组合说明：**

| 知识库 | 原始文档 | 联网搜索 | 说明 |
|--------|----------|----------|------|
| ✓ | ✓ | ✗ | 从知识库检索+查找原始文档（推荐，默认） |
| ✓ | ✗ | ✗ | 只使用知识库分块内容 |
| ✗ | ✗ | ✓ | 只从网络搜索 |
| ✓ | ✓ | ✓ | 结合知识库、原始文档和网络搜索 |
| ✗ | ✗ | ✗ | 纯对话模式，不查任何资料 |

**原始文档功能说明：**
- 系统会根据知识库检索结果，自动查找对应的原始文档
- 提取知识库 chunks 中提到的页码，并扩展前后页面获取更多上下文
- 原始文档内容会被添加到 LLM 上下文中，提供更完整、更准确的信息
- 需要在「管理」页配置原始文档搜索路径

**其他功能：**
- 对话历史会自动保留，多轮对话上下文连贯
- 消息悬停时显示「复制」和「重发」按钮
- 思考型模型的思考过程以灰色区分展示

---

## 六、知识库管理

点击「🗄 管理」标签可以：

- **查看统计信息**：文档总数、向量块数、数据库大小、embedding 模型
- **配置原始文档路径**：添加本地文件夹路径，系统会在这些路径中查找原始文档
- **导出备份**：将知识库导出为 JSON 文件（包含文档和向量）
- **导入备份**：从 JSON 文件恢复知识库
- **删除文档**：逐个删除文档及其向量数据
- **重置知识库**：清空所有数据（需二次确认）

### 原始文档搜索路径配置

1. 在「管理」页找到「原始文档搜索路径」区域
2. 输入本地文件夹路径（如 `/Users/username/Documents`）
3. 点击「添加」按钮
4. 系统会在这些路径中递归查找与知识库文档标题匹配的原始文件

**工作原理：**
- 当用户提问时，系统先从知识库检索相关 chunks
- 根据 chunk 所属的文档标题，在配置的路径中查找原始文件
- 支持 `.md`、`.txt`、`.pdf`、`.docx` 等格式
- 自动提取 chunks 中提到的页码，扩展前后页面获取更多上下文

### Embedding 模型检查

导入备份时，系统会自动检查：
- 备份文件使用的 embedding 模型
- 当前数据库使用的 embedding 模型

如果两者不匹配，会提示错误，要求先在「设置」页切换到相同的模型。

---

## 七、搜索知识库

点击「🔍 查询」标签，直接搜索知识库内容：

- 系统同时进行向量语义搜索和 BM25 关键词搜索
- 结果按 RRF 算法融合排名
- 每条结果显示所属文档 ID 和匹配度百分比

---

## 八、数据备份与迁移

### 方式一：使用管理界面（推荐）

1. 导出：在「管理」页点击「📥 导出备份」
2. 导入：在「管理」页点击「📤 导入备份」

导出的 JSON 文件包含：
- 所有文档内容
- 所有向量数据（embedding）
- embedding 模型配置

### 方式二：PostgreSQL 原始备份

```bash
# 备份数据库
pg_dump -U codex codex_db > codex_backup.sql

# 恢复数据库
psql -U codex codex_db < codex_backup.sql
```

### 迁移到新电脑

```bash
# 旧电脑 - 导出备份
在「管理」页点击「导出备份」

# 新电脑
1. bash deploy.sh                              # 先部署环境
2. 启动服务后，在「管理」页点击「导入备份」
3. 或复制 .env 后使用 pg_dump 恢复
```

---

## 九、故障排查

### 后端无法启动

查看日志：
```bash
tail -50 backend/backend.log
```

常见原因：
- **PostgreSQL 未运行**：`brew services start postgresql@15`（macOS）
- **端口 8001 被占用**：`lsof -ti :8001 | xargs kill`
- **Python 包缺失**：`cd backend && source venv/bin/activate && pip install -r requirements.txt`

### 前端无法连接后端

确认后端已启动：
```bash
curl --noproxy localhost http://localhost:8001/chat/config
```

如果使用了系统代理，可能需要将 `localhost` 加入代理排除列表。

### 模型下载慢

本地 embedding 模型默认从 HuggingFace 下载，国内访问较慢，可使用镜像：

```bash
export HF_ENDPOINT=https://hf-mirror.com
bash start.sh
```

### 对话 500 错误

通常是大模型 API 配置问题：
1. 检查「设置」页的 Base URL、API Key、模型名是否正确
2. 查看后端日志：`tail -50 backend/backend.log`
3. 验证 API Key 是否有效（尝试直接调用 API）

### Embedding 模型不匹配

如果在导入备份时出现模型不匹配错误：
1. 确认备份文件使用的模型（在导出文件中有记录）
2. 在「设置」页切换到相同的 embedding 模型
3. 如需使用新模型，需先在「管理」页重置知识库，重新上传文档

---

## 十、更新依赖

```bash
# 更新 Python 依赖
cd backend
source venv/bin/activate
pip install -r requirements.txt --upgrade

# 更新前端依赖
cd frontend
npm install
```
