# Codex 外部 API 文档

Codex 提供 REST API，供外部系统或 AI Agent 调用知识库能力。

## 认证

所有请求需在 Header 中携带 API Key：

```
Authorization: <API_KEY>
```

默认管理 Key 为 `codex-admin-key`，可通过环境变量 `CODEX_ADMIN_KEY` 自定义。

---

## 接口列表

### 健康检查

```
GET /api/v1/api/health
```

**响应示例**

```json
{"status": "ok", "service": "Codex API", "version": "0.2.2"}
```

---

### 统计信息

```
GET /api/v1/api/stats
```

**响应示例**

```json
{
  "document_count": 1353,
  "chunk_count": 9035,
  "embedding_provider": "doubao",
  "embedding_model": "doubao-embedding-vision-251215"
}
```

---

### 搜索知识库

```
POST /api/v1/api/search
```

**请求体**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | 是 | - | 搜索关键词或问题 |
| top_k | int | 否 | 5 | 返回结果数量 |

**请求示例**

```bash
curl -X POST http://localhost:8001/api/v1/api/search \
  -H "Authorization: codex-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "RK3588 芯片规格", "top_k": 5}'
```

**响应示例**

```json
[
  {
    "content": "RK3588 是瑞芯微推出的旗舰级 SoC...",
    "document_id": 42,
    "similarity": 0.85
  }
]
```

---

### 对话

```
POST /api/v1/api/chat
```

**请求体**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | 是 | - | 问题 |
| use_rag | bool | 否 | true | 是否使用知识库 |
| use_web_search | bool | 否 | false | 是否联网搜索 |
| use_original_doc | bool | 否 | true | 是否查找原始文档 |
| top_k | int | 否 | 5 | 检索 chunk 数量 |

**请求示例**

```bash
curl -X POST http://localhost:8001/api/v1/api/chat \
  -H "Authorization: codex-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "RK3588 支持哪些接口？", "use_rag": true}'
```

**响应示例**

```json
{
  "answer": "RK3588 支持 USB 3.0、PCIe 3.0、HDMI 2.1...",
  "sources": [
    {
      "content": "RK3588 接口规格...",
      "document_id": 42,
      "similarity": 0.85
    }
  ],
  "web_sources": []
}
```

---

### 获取文档列表

```
GET /api/v1/api/documents?limit=100&offset=0
```

**Query 参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| limit | int | 100 | 每页数量 |
| offset | int | 0 | 偏移量 |

**响应示例**

```json
{
  "total": 1353,
  "limit": 100,
  "offset": 0,
  "documents": [
    {
      "id": 1,
      "title": "RK3588_datasheet.pdf",
      "file_type": "pdf",
      "created_at": "2026-03-11T10:00:00"
    }
  ]
}
```

---

### 获取文档详情

```
GET /api/v1/api/documents/{document_id}
```

**响应示例**

```json
{
  "id": 1,
  "title": "RK3588_datasheet.pdf",
  "file_type": "pdf",
  "file_size": 2048000,
  "chunk_count": 50,
  "created_at": "2026-03-11T10:00:00"
}
```

---

## 错误码

| HTTP 状态码 | 说明 |
|-------------|------|
| 200 | 成功 |
| 401 | 缺少或无效的 API Key |
| 404 | 资源不存在 |
| 422 | 请求参数错误 |
| 500 | 服务器内部错误 |

**401 响应示例**

```json
{"detail": "缺少 Authorization 头"}
```

---

## Python 调用示例

```python
import requests

BASE_URL = "http://localhost:8001/api/v1/api"
HEADERS = {"Authorization": "codex-admin-key"}

# 搜索
resp = requests.post(f"{BASE_URL}/search", headers=HEADERS,
                     json={"query": "RK3588 芯片规格", "top_k": 3})
results = resp.json()

# 对话
resp = requests.post(f"{BASE_URL}/chat", headers=HEADERS,
                     json={"query": "RK3588 支持哪些接口？", "use_rag": True})
print(resp.json()["answer"])
```

---

## 注意事项

- 如果系统开启了代理，本地请求需绕过代理：`--noproxy localhost`（curl）或设置 `proxies={"http": None}`（Python requests）
- 对话接口在使用原始文档模式（`use_original_doc=true`）时响应较慢（40-60 秒），取决于文档大小
- 默认 `codex-admin-key` 仅适合本地使用，生产环境请通过 `CODEX_ADMIN_KEY` 环境变量设置强密钥
