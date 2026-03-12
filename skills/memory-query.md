name: memory-query
description: Query and chat with the user's local knowledge base. Use this when you need to search the user's documents, notes, or any uploaded knowledge.
version: "1.0"

trigger:
  - when the user asks about something that might be in their knowledge base
  - when the user wants to search their documents or notes
  - when the user wants to add information to their knowledge base

parameters:
  - name: action
    type: string
    required: true
    description: The action to perform (search, chat, add_document, list, stats)
  - name: query
    type: string
    required: false
    description: Search query or chat message
  - name: use_web_search
    type: boolean
    required: false
    description: Whether to also search the web (default: false)
  - name: title
    type: string
    required: false
    description: Document title (for add_document action)
  - name: content
    type: string
    required: false
    description: Document content (for add_document action)

api:
  base_url: http://localhost:8001
  auth:
    type: bearer
    key: memory-admin-key
  endpoints:
    search:
      path: /api/v1/api/search
      method: POST
    chat:
      path: /api/v1/api/chat
      method: POST
    add_document:
      path: /api/v1/api/documents
      method: POST
    list_documents:
      path: /api/v1/api/documents
      method: GET
    stats:
      path: /api/v1/api/stats
      method: GET

examples:
  - user: "搜一下我的笔记里关于 RAG 的内容"
    action: search
    query: "RAG"

  - user: "问一下知识库，Transformer 的原理是什么"
    action: chat
    query: "Transformer 的原理是什么"
    use_web_search: false

  - user: "帮我记一下，RAG 是检索增强生成"
    action: add_document
    title: "RAG 定义"
    content: "RAG（Retrieval-Augmented Generation，检索增强生成）是一种结合检索系统和生成模型的 AI 技术..."

  - user: "我的知识库里有多少文档"
    action: stats
