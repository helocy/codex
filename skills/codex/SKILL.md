# codex-search Skill

_访问用户本地知识库，通过检索增强生成（RAG）回答问题_

## 触发条件

当用户询问：
- 搜索知识库/文档/笔记
- 问知识库问题
- 查询某个主题的相关内容
- 想了解知识库状态

## 配置

**API 地址**: `http://localhost:8001`
**认证**: Bearer token `codex-admin-key`

### 端点

| 操作 | 端点 | 方法 |
|------|------|------|
| 搜索 | `/api/v1/api/search` | POST |
| 对话(RAG) | `/api/v1/api/chat` | POST | 支持 `use_web_search: true` 自动结合网络 |
| 添加文档 | `/api/v1/api/documents` | POST |
| 列出文档 | `/api/v1/api/documents` | GET |
| 统计 | `/api/v1/api/stats` | GET |

## 使用方法

### 策略：知识库优先 + 网络搜索备用

**始终设置 `use_web_search: true`**，这样：
1. 优先使用知识库内容回答（sources）
2. 知识库找不到时，自动结合网络搜索（web_sources）

### 1. 搜索知识库
```bash
curl -X POST http://localhost:8001/api/v1/api/search \
  -H "Authorization: codex-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "你的问题", "top_k": 5}'
```

### 2. 对话（带 RAG + 网络搜索）

**推荐用法**: 设置 `use_web_search: true`，知识库找不到时自动结合网络搜索

```bash
curl -X POST http://localhost:8001/api/v1/api/chat \
  -H "Authorization: codex-admin-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "你的问题",
    "use_rag": true,
    "use_web_search": true,
    "top_k": 5
  }'
```

**返回字段说明**:
- `answer`: 最终回答
- `sources`: 知识库来源文档
- `web_sources`: 网络搜索来源（当 use_web_search: true 时）

### 3. 查看知识库状态
```bash
curl http://localhost:8001/api/v1/api/stats \
  -H "Authorization: codex-admin-key"
```

## 示例对话

- 用户: "搜索一下我笔记里关于 RAG 的内容" → 执行 search
- 用户: "问一下知识库，Transformer 的原理是什么" → 执行 chat (use_web_search: true)
- 用户: "查一下 RV1126B 编码器最大能力" → 执行 chat (优先知识库，找不到则用网络)
- 用户: "我的知识库有多少文档" → 执行 stats

## 回答策略

1. **优先使用知识库**: 知识库的回答更贴近用户的实际文档
2. **知识库无答案时**: 自动结合网络搜索结果补充
3. **明确告知来源**: 回答时说明答案来自知识库还是网络搜索

## 注意事项

- 知识库服务必须运行在 localhost:8001
- 如果服务未启动，返回友好提示让用户启动服务
