English | [中文](README.md)

# Codex - Local AI Knowledge Base

Codex is a local knowledge base management system based on RAG (Retrieval-Augmented Generation) technology, supporting document upload, vector storage, semantic search, and intelligent conversation.

## ✨ Core Features

- 🔍 **Hybrid Retrieval**: BM25 keyword search + vector semantic search, fused with RRF ranking algorithm
- 🌳 **PageIndex Tree Index**: Inspired by VectifyAI/PageIndex, generates hierarchical document trees; LLM navigates chapters for precise retrieval
- 📄 **Multi-format Support**: Markdown (structure-aware chunking), PDF (page-based chunking), Word, plain text
- 🤖 **Intelligent Conversation**: Supports RAG mode, web search, and original document lookup
- 🌐 **Multi-model Compatible**: Supports Doubao, Qwen, OpenAI, Ollama, and other LLMs
- 🎯 **Original Document Lookup**: Automatically finds and uses complete original documents for more accurate answers
- 💾 **Data Backup**: Export/import knowledge base (includes vector data and tree index)
- 🔐 **Local Deployment**: All data stored locally, privacy protected
- 🔌 **External API**: REST API for AI Agent integration

## 🚀 Quick Start

### One-click Install (Recommended)

Works on macOS / Ubuntu / Debian. Paste the following command in your terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/helocy/codex/main/install.sh | bash
```

The script automatically handles: clone repo → install system dependencies (PostgreSQL 15, pgvector, Node.js, Python) → configure database → install Python/frontend dependencies → generate startup scripts.

> First install takes 5–15 minutes (mainly downloading the embedding model ~500MB)

### Manual Deployment

If you've already cloned the repo, run the deployment script directly:

```bash
git clone https://github.com/helocy/codex.git
cd codex
bash deploy.sh
```

### Start Services

```bash
bash start.sh
```

Access:
- Local: http://localhost:5173
- LAN: http://&lt;your-IP&gt;:5173 (shown automatically on startup)
- API docs: http://localhost:8001/docs

### Stop Services

```bash
bash stop.sh
```

See [Quick Start Guide](docs/QUICKSTART.md) for detailed instructions.

## 📚 Main Features

### 1. Knowledge Base Management

- Upload single files or batch upload directories
- Automatic vectorization and chunk storage
- Supports Markdown, PDF, Word, plain text
- Duplicate detection (similarity check)

### 2. Intelligent Conversation

- **Knowledge Base Mode**: Answer questions based on uploaded documents
- **Original Document Mode**: Find and use complete original documents (recommended)
- **Web Search Mode**: Retrieve real-time information from the internet
- **Hybrid Mode**: Combine knowledge base, original documents, and web search

### 3. Original Document Lookup

The system automatically finds original documents based on knowledge base retrieval:
- Configure local folder paths
- Automatically match document titles
- Extract page numbers and expand context
- Supports PDF, Markdown, Word, and more

### 4. Advanced Search

- Vector semantic search (embedding-based)
- BM25 keyword search
- RRF fusion ranking
- Comparative query optimization (entity extraction, multi-query retrieval)
- **PageIndex Two-phase Retrieval**: LLM navigates the document tree to locate chapters, then performs fine-grained retrieval within target sections

### 5. Data Management

- View statistics (document count, vector chunk count, database size)
- Export/import backups (including vector data)
- Embedding model compatibility check
- Document deletion and knowledge base reset
- **Duplicate Detection**: Find redundant documents using vector similarity + filename similarity; supports individual or batch deletion
- Settings page Tab layout (Model Config / Database / Documents)

### 6. External API (AI Agent Integration)

Complete REST API for external systems or AI Agents:

```bash
# Search knowledge base
curl -X POST http://localhost:8001/api/v1/api/search \
  -H "Authorization: codex-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "your question", "top_k": 5}'

# Chat
curl -X POST http://localhost:8001/api/v1/api/chat \
  -H "Authorization: codex-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "your question", "use_rag": true}'
```

See [docs/API.md](docs/API.md) for full API documentation.

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI
- **Database**: PostgreSQL
- **Vector Search**: pgvector (vector search) + rank_bm25 (keyword search)
- **Embedding**: sentence-transformers / Doubao Embedding / OpenAI-compatible
- **LLM**: OpenAI-compatible API (Doubao, Qwen, Ollama, etc.)

### Frontend
- **Framework**: React + TypeScript + Vite
- **Styling**: Tailwind CSS
- **Markdown Rendering**: react-markdown + remark-gfm

## 📖 Documentation

- [Quick Start Guide](docs/QUICKSTART.md) - Deployment, configuration, and usage
- [API Reference](docs/API.md) - External API documentation
- [Architecture Whitepaper](docs/产品需求与架构白皮书.md) - Technical architecture and design

## 🔧 Configuration

### LLM Configuration

Supports any OpenAI-compatible API:

```
# Doubao
Base URL: https://ark.cn-beijing.volces.com/api/v3
Model: doubao-seed-1-6-251015

# Qwen
Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1
Model: qwen-plus

# OpenAI
Base URL: https://api.openai.com/v1
Model: gpt-4o

# Ollama (local)
Base URL: http://localhost:11434/v1
Model: llama3
```

### Embedding Configuration

Three embedding providers supported:

| Provider | Model | Notes |
|----------|-------|-------|
| Local | paraphrase-multilingual-MiniLM-L12-v2 | Free, default, no API key needed |
| Doubao | doubao-embedding-vision-251215 | Requires Doubao API key, 2048 dimensions |
| OpenAI-compatible | text-embedding-3-small | Requires API key |

> ⚠️ After switching embedding models, you must reset the knowledge base and re-upload all documents.

### Original Document Path Configuration

Add local folder paths in the "Config" page. The system will search these paths for original documents:

```
/Users/username/Documents
/Users/username/Projects
```

## 🎯 Use Cases

- **Personal Knowledge Management**: Organize notes, documents, and study materials
- **Technical Documentation Query**: Quickly search API docs and technical specs
- **Project Resource Management**: Manage design documents and requirements
- **Research Material Organization**: Smart retrieval for papers, reports, and research notes
- **AI Agent Integration**: Provide knowledge base capabilities via API

## 📝 Changelog

### v0.7.0 (2026-04-02)

- Memory optimization: free Python float lists after building numpy embedding matrix, reducing RSS from 4.4 GB to ~1.1 GB
- Two-level PDF cache: L1 caches PdfReader objects, L2 caches extracted page text; repeated access requires no re-parsing
- Original document lookup now uses the database-stored file path directly (O(1)) instead of directory scanning (was 4.75s)
- Fixed admin stats/delete endpoints crashing due to VACUUM inside a transaction aborting the PostgreSQL session
- Fixed login hang in proxy environments: added NO_PROXY to both start.sh and deploy.sh-generated startup scripts
- Fixed socks:// proxy scheme incompatibility with httpx; auto-normalizes to socks5://
- Deploy optimization: skip torch (~2 GB) install when using API embedding; pre-download local model with progress display

### v0.6.0 (2026-03-30)

- User management merged into config page as a dedicated "Users" sub-tab; removed the standalone top-level tab
- Fixed login 500 error caused by passlib 1.7.4 incompatibility with bcrypt 4.0.1; now uses bcrypt directly
- Username change returns a new token from the backend; frontend refreshes session automatically without re-login
- Username display in top-right corner: admin shown in bold red, regular users in blue
- Fixed "Not Found" / "Not authenticated" errors when saving account changes

### v0.5.0 (2026-03-30)

- All source sections (source analysis, knowledge base, original docs, matched chapters) now support collapsible toggle, collapsed by default for a cleaner UI
- Chat model thinking process supports collapsible toggle, collapsed by default
- Full source code analysis result is passed to the chat model for comprehensive reasoning
- Source analysis rendering improved: body text is uniform small gray, only code blocks retain formatting
- Dividers added between source sections
- Code analysis enabled by default
- Fixed PDF original document parsing failure (installed pypdf)
- Fixed `<think>/<thinking>` tags leaking into source analysis output
- Fixed source analysis detail not displaying
- Updated version to v0.5.0

### v0.4.1 (2026-03-18)

- Upgraded deploy wizard: `deploy.sh` now features step-by-step interactive setup, supporting provider selection (Doubao/Qwen/OpenAI/Ollama/Custom), provider-specific prompts, hidden API key input, and a summary confirmation before writing `.env`
- Added generic LLM environment variable support (`LLM_PROVIDER/LLM_API_KEY/LLM_BASE_URL/LLM_MODEL`), backward-compatible with `DOUBAO_API_KEY`
- Document list now shows tree index status (🌳 green = indexed, gray = not built) with a batch build button for missing indexes
- Fixed Ubuntu OS being displayed as "debian" in deploy output
- Added English README (`README_EN.md`) with language toggle

### v0.4.0 (2026-03-18)

- Added PageIndex tree index: documents automatically generate hierarchical chapter trees on upload (JSONB storage); Markdown parses headings directly, PDF/text uses LLM for structure extraction
- Two-phase retrieval: LLM locates relevant sections from compact tree summaries (top-15 BM25 pre-filter), then hybrid vector+BM25 search within target chunks, with full-search fallback for guaranteed recall
- `chunks.section_id` field links chunks to tree nodes for section-based filtering
- Chat response now includes `tree_nodes` field; frontend displays matched sections (document › chapter)
- Fixed export/import backup missing `tree_index` and `section_id`

### v0.3.0 (2026-03-13)

- Added internationalization: full Chinese/English bilingual UI, auto-detects browser language, supports manual switching
- Version number unified to 0.3.0

### v0.2.3 (2026-03-12)

- Full Ubuntu/Debian support: PostgreSQL 15 + pgvector via PGDG official repo, Node.js upgraded to 20 LTS
- macOS: auto-compile and install pgvector from source
- Added `install.sh` one-click installer, supports `curl | bash` zero-config install
- Auto-display LAN access address on startup
- Fixed CORS restrictions for LAN multi-device access

### v0.2.2 (2026-03-12)

- Merged "Settings" and "Admin" pages into unified "Config" page
- Config page added document keyword search (real-time filter + highlight matching)
- LAN access support (Vite listens on all interfaces, fixed CORS)
- Management features (model config, original doc paths, import/reset/delete) hidden on non-localhost access

### v0.2.1 (2026-03-12)

- Fixed start-backend.sh / start-frontend.sh path errors
- Optimized document upload: similarity check changed from full scan (10069 chunks) to first chunk only (105 rows), 96x speed improvement
- Fixed Doubao Embedding API batch limitation with concurrent requests (up to 5), ~2x upload speed improvement
- Improved external API documentation

### v0.2.0 (2026-03-11)

- Added force upload (skip duplicate detection)
- Added overwrite upload (replace same-name documents)
- Optimized original document lookup status display
- Improved conversation UI information layout

### v0.1.0 (2026-03-01)

- Core RAG features (document upload, vectorization, semantic search)
- Hybrid retrieval (BM25 + vector search + RRF fusion)
- Multi-format support (Markdown, PDF, Word, plain text)
- Intelligent conversation (RAG mode, web search, multi-turn dialogue)
- Original document lookup
- Comparative query optimization (entity extraction, multi-query retrieval)
- Data backup and restore
- Embedding model compatibility check
- Web UI (React + TypeScript)

## 🤝 Contributing

Issues and Pull Requests are welcome!

## 👤 Author

Zhichao

## 📄 License

MIT License

## 🙏 Acknowledgements

- [sentence-transformers](https://www.sbert.net/) - Local embedding model
- [pgvector](https://github.com/pgvector/pgvector) - PostgreSQL vector extension
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [React](https://react.dev/) - Frontend framework
