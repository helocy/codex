# Codex Knowledge Base Skill

## 概述

这个 skill 允许 AI Agent 访问用户的本地知识库，执行搜索、对话和文档管理操作。

## 配置

### 环境变量

- `MEMORY_API_URL`: Codex API 地址（默认: http://localhost:8001）
- `MEMORY_API_KEY`: API 认证密钥（默认: codex-admin-key）

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/api/search` | POST | 搜索知识库 |
| `/api/v1/api/chat` | POST | 对话（支持 RAG） |
| `/api/v1/api/documents` | GET | 列出文档 |
| `/api/v1/api/documents` | POST | 添加文档 |
| `/api/v1/api/documents/{id}` | DELETE | 删除文档 |
| `/api/v1/api/stats` | GET | 获取统计信息 |
| `/api/v1/api/health` | GET | 健康检查 |

## 使用方法

### 1. 搜索知识库

```python
import requests

def search_knowledge_base(query: str, top_k: int = 5) -> list:
    """搜索知识库中的相关内容"""
    response = requests.post(
        "http://localhost:8001/api/v1/api/search",
        headers={"Authorization": "codex-admin-key"},
        json={"query": query, "top_k": top_k}
    )
    return response.json()

# 使用示例
results = search_knowledge_base("什么是 RAG")
for r in results:
    print(f"文档 #{r['document_id']} (相似度: {r['similarity']:.2%})")
    print(f"内容: {r['content'][:200]}...")
```

### 2. 对话（带 RAG）

```python
def chat_with_knowledge_base(
    query: str,
    use_rag: bool = True,
    use_web_search: bool = False,
    use_original_doc: bool = True
) -> dict:
    """与知识库对话"""
    response = requests.post(
        "http://localhost:8001/api/v1/api/chat",
        headers={"Authorization": "codex-admin-key"},
        json={
            "query": query,
            "use_rag": use_rag,
            "use_web_search": use_web_search,
            "use_original_doc": use_original_doc,
            "top_k": 5
        }
    )
    return response.json()

# 使用示例
result = chat_with_knowledge_base("请解释 RAG 的原理")
print(f"回答: {result['answer']}")
print(f"来源文档: {result['sources']}")
print(f"网络来源: {result['web_sources']}")

# 使用原始文档功能
result = chat_with_knowledge_base(
    "RV1126B的芯片规格是什么？",
    use_rag=True,
    use_original_doc=True  # 启用原始文档查找
)
print(f"回答: {result['answer']}")
```

### 3. 添加文档

```python
def add_document(title: str, content: str, file_type: str = "text") -> dict:
    """添加文档到知识库"""
    response = requests.post(
        "http://localhost:8001/api/v1/api/documents",
        headers={"Authorization": "codex-admin-key"},
        json={
            "title": title,
            "content": content,
            "file_type": file_type
        }
    )
    return response.json()

# 使用示例
result = add_document(
    title="RAG 技术概述",
    content="RAG（检索增强生成）是一种结合检索系统和生成模型的 AI 技术..."
)
print(f"文档 ID: {result['document_id']}")
```

### 4. 列出文档

```python
def list_documents(limit: int = 100, offset: int = 0) -> dict:
    """列出知识库中的文档"""
    response = requests.get(
        f"http://localhost:8001/api/v1/api/documents?limit={limit}&offset={offset}",
        headers={"Authorization": "codex-admin-key"}
    )
    return response.json()

# 使用示例
result = list_documents(limit=10)
for doc in result['documents']:
    print(f"#{doc['id']}: {doc['title']}")
```

### 5. 删除文档

```python
def delete_document(document_id: int) -> dict:
    """删除文档"""
    response = requests.delete(
        f"http://localhost:8001/api/v1/api/documents/{document_id}",
        headers={"Authorization": "codex-admin-key"}
    )
    return response.json()

# 使用示例
result = delete_document(123)
print(result['message'])
```

### 6. 获取统计信息

```python
def get_stats() -> dict:
    """获取知识库统计信息"""
    response = requests.get(
        "http://localhost:8001/api/v1/api/stats",
        headers={"Authorization": "codex-admin-key"}
    )
    return response.json()

# 使用示例
stats = get_stats()
print(f"文档数: {stats['document_count']}")
print(f"向量块数: {stats['chunk_count']}")
print(f"Embedding 模型: {stats['embedding_model']}")
```

## 完整使用示例

```python
import requests

class CodexClient:
    def __init__(self, api_url: str = "http://localhost:8001", api_key: str = "codex-admin-key"):
        self.api_url = api_url
        self.headers = {"Authorization": api_key}

    def search(self, query: str, top_k: int = 5) -> list:
        resp = requests.post(
            f"{self.api_url}/api/v1/api/search",
            headers=self.headers,
            json={"query": query, "top_k": top_k}
        )
        return resp.json()

    def chat(self, query: str, use_rag: bool = True, use_web_search: bool = False, use_original_doc: bool = True) -> dict:
        resp = requests.post(
            f"{self.api_url}/api/v1/api/chat",
            headers=self.headers,
            json={
                "query": query,
                "use_rag": use_rag,
                "use_web_search": use_web_search,
                "use_original_doc": use_original_doc,
                "top_k": 5
            }
        )
        return resp.json()

    def add_document(self, title: str, content: str) -> dict:
        resp = requests.post(
            f"{self.api_url}/api/v1/api/documents",
            headers=self.headers,
            json={"title": title, "content": content, "file_type": "text"}
        )
        return resp.json()

    def list_documents(self, limit: int = 100) -> dict:
        resp = requests.get(
            f"{self.api_url}/api/v1/api/documents?limit={limit}",
            headers=self.headers
        )
        return resp.json()

    def delete_document(self, doc_id: int) -> dict:
        resp = requests.delete(
            f"{self.api_url}/api/v1/api/documents/{doc_id}",
            headers=self.headers
        )
        return resp.json()

    def stats(self) -> dict:
        resp = requests.get(
            f"{self.api_url}/api/v1/api/stats",
            headers=self.headers
        )
        return resp.json()


# 使用示例
client = CodexClient()

# 搜索
results = client.search("RAG 技术")
print(results)

# 对话
result = client.chat("请解释 RAG 是什么")
print(result["answer"])

# 添加文档
client.add_document("新文档", "这是文档内容...")

# 查看统计
print(client.stats())
```

## 注意事项

1. **API Key**: 默认使用 `codex-admin-key`，可在环境变量中配置
2. **Embedding 模型**: 知识库使用的 embedding 模型会影响搜索效果
3. **文档上传**: 通过 API 添加的文档会自动进行向量化
4. **网络搜索**: `use_web_search=True` 会同时从互联网搜索相关信息
5. **原始文档**: `use_original_doc=True` 会查找并使用完整的原始文档内容
   - 需要先在管理界面配置原始文档搜索路径
   - 系统会根据文档标题在配置的路径中递归查找原始文件
   - 支持 `.md`、`.txt`、`.pdf`、`.docx` 等格式
   - 自动提取页码信息并扩展上下文范围

## 原始文档功能详解

### 配置原始文档路径

```python
def add_original_doc_path(path: str) -> dict:
    """添加原始文档搜索路径"""
    response = requests.post(
        "http://localhost:8001/api/v1/admin/original-doc-paths",
        params={"path": path}
    )
    return response.json()

def get_original_doc_paths() -> dict:
    """获取已配置的原始文档路径"""
    response = requests.get(
        "http://localhost:8001/api/v1/admin/original-doc-paths"
    )
    return response.json()

def remove_original_doc_path(path: str) -> dict:
    """移除原始文档搜索路径"""
    response = requests.delete(
        "http://localhost:8001/api/v1/admin/original-doc-paths",
        params={"path": path}
    )
    return response.json()

# 使用示例
add_original_doc_path("/Users/username/Documents")
paths = get_original_doc_paths()
print(f"已配置路径: {paths['paths']}")
```

### 工作原理

1. 用户提问时，系统先从知识库检索相关 chunks
2. 根据 chunk 所属的文档标题，在配置的路径中查找原始文件
3. 提取 chunks 中提到的页码（如 `[第 X 页]`），并扩展前后页面
4. 将原始文档内容添加到 LLM 上下文中
5. LLM 基于原始文档和知识库片段生成更准确的回答

### 优势

- **更完整的信息**：不受知识库分块限制，可以获取完整的原始文档内容
- **更准确的回答**：LLM 可以看到更多上下文，减少信息遗漏
- **页码定位**：自动提取和扩展页码范围，精确定位相关内容
- **多格式支持**：支持 Markdown、PDF、Word 等多种文档格式

