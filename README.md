[English](README_EN.md) | 中文

# Codex - 本地 AI 智能知识库

Codex 是一个基于 RAG（检索增强生成）技术的本地知识库管理系统，支持文档上传、向量化存储、语义搜索和智能对话。

## ✨ 核心特性

- 🔍 **混合检索**：BM25 关键词搜索 + 向量语义搜索，RRF 算法融合排序
- 🌳 **PageIndex 树形索引**：受 VectifyAI/PageIndex 启发，为文档生成层次化目录树，LLM 导航章节后精准检索
- 📄 **多格式支持**：Markdown（感知分块）、PDF（按页分块）、Word、纯文本
- 🤖 **智能对话**：支持 RAG 模式、网络搜索、原始文档查找
- 🌐 **多模型兼容**：支持豆包、通义千问、OpenAI、Ollama 等多种 LLM
- 🎯 **原始文档查找**：自动查找并使用完整原始文档，提供更准确的回答
- 💾 **数据备份**：支持导出/导入知识库（包含向量数据、树形索引）
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
- **PageIndex 两阶段检索**：LLM 先分析文档树定位章节，再在目标章节内精细检索

### 5. 数据管理

- 查看统计信息（文档数、向量块数、数据库大小）
- 导出/导入备份（包含向量数据）
- Embedding 模型兼容性检查
- 文档删除和知识库重置
- **冗余文档检测**：基于向量相似度 + 文件名相似度找出重复文档，支持单独删除或批量清理
- 配置页面 Tab 分组（模型配置 / 数据库配置 / 文档列表）

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

### v0.6.0 (2026-03-30)

- 用户管理合并到配置页，作为独立子标签「用户管理」，移除顶部单独的 tab
- 修复 passlib 1.7.4 与 bcrypt 4.0.1 不兼容导致的登录 500 错误，改用 bcrypt 直接调用
- 修改用户名后后端返回新 token，前端自动刷新 session，无需重新登录
- 右上角用户名样式：管理员红色加粗，普通用户蓝色
- 修复修改账号信息提示 Not Found / Not authenticated 的问题

### v0.5.0 (2026-03-30)

- 源码分析结论、知识库来源、原始文档、命中章节均支持折叠展开，默认折叠，界面更简洁
- 对话模型思考过程支持折叠，默认折叠
- 源码分析结论完整传给对话大模型参与综合分析，权重更高
- 源码分析结论渲染优化：正文统一小字灰色，仅代码块保留格式化，去除多余加粗/标题样式
- 各来源区块之间增加分隔线
- 分析源代码默认勾选
- 修复 PDF 原始文档解析失败（安装 pypdf）
- 修复 `<think>/<thinking>` 标签泄漏到源码分析输出的问题
- 修复源码分析结论不显示的问题
- 版本号更新至 v0.5.0

### v0.4.1 (2026-03-18)

- 部署向导升级：`deploy.sh` 改为交互式分步引导，支持选择大模型提供商（豆包/通义千问/OpenAI/Ollama/自定义），按提供商展示对应参数，API Key 隐藏输入，配置摘要确认后写入 `.env`
- 新增通用 LLM 环境变量支持（`LLM_PROVIDER/LLM_API_KEY/LLM_BASE_URL/LLM_MODEL`），兼容旧版 `DOUBAO_API_KEY`，所有提供商均可通过 `.env` 持久化
- 文档列表新增树形索引状态标记（🌳 绿色=已有索引，灰色=未建立），支持批量构建缺失的树形索引
- 修复 Ubuntu 系统被识别显示为 debian 的问题
- 新增英文 README（README_EN.md），中英文双语切换

### v0.4.0 (2026-03-18)

- 新增 PageIndex 树形索引：文档上传后自动生成层次化目录树（JSONB 存储），Markdown 直接解析标题，PDF/文本调用 LLM 提取章节结构
- 两阶段检索：LLM 先从压缩树摘要中定位相关章节（Top-15 BM25 预筛），再在目标 chunks 内做向量+BM25 混合检索，全量检索兜底保证召回
- `chunks.section_id` 字段关联 chunk 与树节点，检索时按节点过滤
- 对话响应新增 `tree_nodes` 字段，前端展示命中章节（文档 › 章节）
- 修复导出/导入备份漏掉 `tree_index` 和 `section_id` 的问题

### v0.3.0 (2026-03-13)

- 新增国际化支持：完整的中英文双语界面，自动检测浏览器语言，支持手动切换
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
