# Codex - 本地 AI 智能知识库

Codex 是一个基于 RAG（检索增强生成）技术的本地知识库管理系统，支持文档上传、向量化存储、语义搜索和智能对话。

## ✨ 核心特性

- 🔍 **混合检索**：BM25 关键词搜索 + 向量语义搜索，RRF 算法融合排序
- 📄 **多格式支持**：Markdown（感知分块）、PDF（按页分块）、Word、纯文本
- 🤖 **智能对话**：支持 RAG 模式、网络搜索、原始文档查找
- 🌐 **多模型兼容**：支持豆包、通义千问、OpenAI、Ollama 等多种 LLM
- 🎯 **原始文档查找**：自动查找并使用完整原始文档，提供更准确的回答
- 💾 **数据备份**：支持导出/导入知识库（包含向量数据）
- 🔐 **本地部署**：数据完全本地存储，保护隐私
- 🔌 **外部 API**：提供 REST API，支持 AI Agent 集成

## 🚀 快速开始

### 一键安装（推荐）

macOS / Ubuntu / Debian 通用，复制以下命令到终端执行：

```bash
curl -fsSL https://raw.githubusercontent.com/helocy/codex/main/install.sh | bash
```

脚本会自动完成：克隆代码 → 安装系统依赖（PostgreSQL 15、pgvector、Node.js、Python）→ 配置数据库 → 安装 Python/前端依赖 → 生成启动脚本。

> 首次安装约需 5–15 分钟（主要是下载 embedding 模型 ~500MB）

### 手动部署

如果已克隆仓库，直接运行部署脚本：

```bash
git clone https://github.com/helocy/codex.git
cd codex
bash deploy.sh
```

### 启动服务

```bash
bash start.sh
```

访问：
- 本机：http://localhost:5173
- 局域网：http://&lt;本机IP&gt;:5173（启动后自动显示）
- API 文档：http://localhost:8001/docs

### 停止服务

```bash
bash stop.sh
```

详细使用说明请查看 [快速启动指南](docs/QUICKSTART.md)

## 📚 主要功能

### 1. 知识库管理

- 上传单个文件或批量上传目录
- 自动向量化和分块存储
- 支持 Markdown、PDF、Word、纯文本
- 文档去重检测（相似度检查）

### 2. 智能对话

- **知识库模式**：基于上传的文档回答问题
- **原始文档模式**：查找并使用完整原始文档（推荐）
- **网络搜索模式**：从互联网获取实时信息
- **混合模式**：结合知识库、原始文档和网络搜索

### 3. 原始文档功能

系统会根据知识库检索结果，自动查找对应的原始文档：
- 配置本地文件夹路径
- 自动匹配文档标题
- 提取页码信息并扩展上下文
- 支持 PDF、Markdown、Word 等格式

### 4. 高级搜索

- 向量语义搜索（基于 embedding）
- BM25 关键词搜索
- RRF 算法融合排序
- 对比查询优化（自动提取实体，多查询检索）

### 5. 数据管理

- 查看统计信息（文档数、向量块数、数据库大小）
- 导出/导入备份（包含向量数据）
- Embedding 模型兼容性检查
- 文档删除和知识库重置

### 6. 外部 API（AI Agent 集成）

提供完整的 REST API，可供外部系统或 AI Agent 调用：

```bash
# 搜索知识库
curl -X POST http://localhost:8001/api/v1/api/search \
  -H "Authorization: codex-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "你的问题", "top_k": 5}'

# 对话
curl -X POST http://localhost:8001/api/v1/api/chat \
  -H "Authorization: codex-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "你的问题", "use_rag": true}'
```

详细 API 文档见 [docs/API.md](docs/API.md)

## 🛠️ 技术栈

### 后端
- **框架**：FastAPI
- **数据库**：PostgreSQL
- **向量检索**：pgvector（向量搜索）+ rank_bm25（关键词搜索）
- **Embedding**：sentence-transformers / 豆包 Embedding / OpenAI 兼容
- **LLM**：支持 OpenAI 兼容接口（豆包、通义千问、Ollama 等）

### 前端
- **框架**：React + TypeScript + Vite
- **样式**：Tailwind CSS
- **Markdown 渲染**：react-markdown + remark-gfm

## 📖 文档

- [快速启动指南](docs/QUICKSTART.md) - 部署、配置和使用说明
- [API 使用指南](docs/API.md) - 外部 API 接口文档
- [产品需求与架构白皮书](docs/产品需求与架构白皮书.md) - 详细的技术架构和设计思路

## 🔧 配置说明

### LLM 配置

支持任何 OpenAI 兼容的 API：

```bash
# 豆包
Base URL: https://ark.cn-beijing.volces.com/api/v3
Model: doubao-seed-1-6-251015

# 通义千问
Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1
Model: qwen-plus

# OpenAI
Base URL: https://api.openai.com/v1
Model: gpt-4o

# Ollama（本地）
Base URL: http://localhost:11434/v1
Model: llama3
```

### Embedding 配置

支持三种 embedding 模型：

| 提供商 | 模型 | 说明 |
|--------|------|------|
| 本地 | paraphrase-multilingual-MiniLM-L12-v2 | 免费，默认，无需 API Key |
| 豆包 | doubao-embedding-vision-251215 | 需要豆包 API Key，向量维度 2048 |
| OpenAI 兼容 | text-embedding-3-small | 需要 API Key |

> ⚠️ 更换 embedding 模型后，需要重置知识库并重新上传文档。

### 原始文档路径配置

在「配置」页面添加本地文件夹路径，系统会在这些路径中查找原始文档：

```
/Users/username/Documents
/Users/username/Projects
```

## 🎯 使用场景

- **个人知识管理**：整理笔记、文档、学习资料
- **技术文档查询**：快速检索 API 文档、技术规范
- **项目资料管理**：管理项目相关的设计文档、需求文档
- **研究资料整理**：论文、报告、研究笔记的智能检索
- **AI Agent 集成**：通过 API 为 AI Agent 提供知识库能力

## 📝 版本历史

### v0.3.0 (2026-03-12)

- 版本号统一更新至 0.3.0

### v0.2.3 (2026-03-12)

- Ubuntu/Debian 完整支持：通过 PGDG 官方源安装 PostgreSQL 15 + pgvector，Node.js 升至 20 LTS
- macOS：自动从源码编译安装 pgvector
- 新增 `install.sh` 一键安装脚本，支持 `curl | bash` 方式零配置安装
- 启动时自动显示局域网访问地址
- 修复 CORS 跨域限制，支持局域网多设备访问

### v0.2.2 (2026-03-12)

- 合并「设置」和「管理」页面为统一的「配置」页面
- 配置页新增文档关键词搜索（实时过滤 + 高亮匹配）
- 支持局域网访问（Vite 监听所有网卡，修复 CORS 跨域限制）
- 非 localhost 访问时隐藏管理功能（模型配置、原始文档路径、导入/重置/删除操作）

### v0.2.1 (2026-03-12)

- 修复 start-backend.sh / start-frontend.sh 路径错误
- 优化文档上传性能：相似度检查从全量扫描（10069 chunks）改为仅扫描首 chunk（105 条），速度提升 96x
- 修复豆包 Embedding API 不支持批量的问题，改为并发请求（最多 5 并发），上传速度提升约 2x
- 完善外部 API 文档

### v0.2.0 (2026-03-11)

- 新增强制上传功能（跳过相似文档检测）
- 新增覆盖上传功能（覆盖同名文档）
- 优化原始文档查找状态显示
- 改进对话界面信息展示结构

### v0.1.0 (2026-03-01)

- 基础 RAG 功能（文档上传、向量化、语义搜索）
- 混合检索（BM25 + 向量搜索 + RRF 融合）
- 多格式支持（Markdown、PDF、Word、纯文本）
- 智能对话（支持 RAG、网络搜索、多轮对话）
- 原始文档查找功能
- 对比查询优化（实体提取、多查询检索）
- 数据备份与恢复
- Embedding 模型兼容性检查
- Web 界面（React + TypeScript）

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 👤 作者

Zhichao

## 📄 许可证

MIT License

## 🙏 致谢

- [sentence-transformers](https://www.sbert.net/) - 本地 embedding 模型
- [pgvector](https://github.com/pgvector/pgvector) - PostgreSQL 向量扩展
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的 Python Web 框架
- [React](https://react.dev/) - 前端框架
