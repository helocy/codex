"""
Memory Knowledge Base - Python Client
=====================================

这个模块提供了与 Memory 知识库交互的 Python 客户端。

安装:
    pip install requests

使用示例:
    from memory_client import MemoryClient

    client = MemoryClient()

    # 搜索
    results = client.search("RAG")

    # 对话
    result = client.chat("什么是 RAG")

    # 添加文档
    client.add_document("标题", "内容")
"""

import os
import requests
from typing import Optional, List, Dict, Any


class MemoryClient:
    """Memory 知识库 Python 客户端"""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        初始化客户端

        Args:
            api_url: API 地址，默认从环境变量 MEMORY_API_URL 获取
            api_key: API 密钥，默认从环境变量 MEMORY_API_KEY 获取
        """
        self.api_url = api_url or os.environ.get("MEMORY_API_URL", "http://localhost:8001")
        self.api_key = api_key or os.environ.get("MEMORY_API_KEY", "memory-admin-key")
        self.headers = {"Authorization": self.api_key}

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """发送 API 请求"""
        url = f"{self.api_url}{path}"
        return requests.request(method, url, headers=self.headers, **kwargs)

    # ── 搜索 ───────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        搜索知识库

        Args:
            query: 搜索关键词
            top_k: 返回结果数量

        Returns:
            搜索结果列表，每项包含 content, document_id, similarity
        """
        resp = self._request(
            "POST",
            "/api/v1/api/search",
            json={"query": query, "top_k": top_k}
        )
        resp.raise_for_status()
        return resp.json()

    # ── 对话 ───────────────────────────────────────────────────────────────

    def chat(
        self,
        query: str,
        use_rag: bool = True,
        use_web_search: bool = False,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        与知识库对话

        Args:
            query: 用户问题
            use_rag: 是否使用知识库（默认 True）
            use_web_search: 是否使用网络搜索（默认 False）
            top_k: 检索的文档数量

        Returns:
            包含 answer, sources, web_sources 的字典
        """
        resp = self._request(
            "POST",
            "/api/v1/api/chat",
            json={
                "query": query,
                "use_rag": use_rag,
                "use_web_search": use_web_search,
                "top_k": top_k
            }
        )
        resp.raise_for_status()
        return resp.json()

    # ── 文档管理 ───────────────────────────────────────────────────────────

    def add_document(
        self,
        title: str,
        content: str,
        file_type: str = "text"
    ) -> Dict[str, Any]:
        """
        添加文档到知识库

        Args:
            title: 文档标题
            content: 文档内容
            file_type: 文件类型（默认 text）

        Returns:
            包含 document_id, chunk_count 的字典
        """
        resp = self._request(
            "POST",
            "/api/v1/api/documents",
            json={
                "title": title,
                "content": content,
                "file_type": file_type
            }
        )
        resp.raise_for_status()
        return resp.json()

    def list_documents(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        列出文档

        Args:
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            包含 total, documents 的字典
        """
        resp = self._request(
            "GET",
            f"/api/v1/api/documents?limit={limit}&offset={offset}"
        )
        resp.raise_for_status()
        return resp.json()

    def delete_document(self, document_id: int) -> Dict[str, Any]:
        """
        删除文档

        Args:
            document_id: 文档 ID

        Returns:
            包含 message 的字典
        """
        resp = self._request(
            "DELETE",
            f"/api/v1/api/documents/{document_id}"
        )
        resp.raise_for_status()
        return resp.json()

    # ── 统计 ───────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """
        获取知识库统计信息

        Returns:
            包含 document_count, chunk_count, embedding_model 等信息
        """
        resp = self._request("GET", "/api/v1/api/stats")
        resp.raise_for_status()
        return resp.json()

    # ── 健康检查 ───────────────────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            包含 status, service, version 的字典
        """
        resp = self._request("GET", "/api/v1/api/health")
        resp.raise_for_status()
        return resp.json()


# ── 便捷函数 ───────────────────────────────────────────────────────────────

def search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """快速搜索函数"""
    return MemoryClient().search(query, top_k)


def chat(
    query: str,
    use_rag: bool = True,
    use_web_search: bool = False
) -> str:
    """快速对话函数，返回回答文本"""
    result = MemoryClient().chat(query, use_rag, use_web_search)
    return result["answer"]


def add_document(title: str, content: str) -> int:
    """快速添加文档函数，返回文档 ID"""
    result = MemoryClient().add_document(title, content)
    return result["document_id"]


# ── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Memory Knowledge Base CLI")
    subparsers = parser.add_subparsers(dest="command")

    # search 命令
    search_parser = subparsers.add_parser("search", help="搜索知识库")
    search_parser.add_argument("query", help="搜索关键词")
    search_parser.add_argument("--top-k", type=int, default=5, help="返回结果数量")

    # chat 命令
    chat_parser = subparsers.add_parser("chat", help="与知识库对话")
    chat_parser.add_argument("query", help="问题内容")
    chat_parser.add_argument("--no-rag", action="store_true", help="不使用知识库")
    chat_parser.add_argument("--web", action="store_true", help="使用网络搜索")

    # stats 命令
    subparsers.add_parser("stats", help="查看统计信息")

    # add 命令
    add_parser = subparsers.add_parser("add", help="添加文档")
    add_parser.add_argument("title", help="文档标题")
    add_parser.add_argument("content", help="文档内容")

    args = parser.parse_args()
    client = MemoryClient()

    if args.command == "search":
        results = client.search(args.query, args.top_k)
        for r in results:
            print(f"\n文档 #{r['document_id']} (相似度: {r['similarity']:.2%})")
            print(r["content"])

    elif args.command == "chat":
        result = client.chat(
            args.query,
            use_rag=not args.no_rag,
            use_web_search=args.web
        )
        print(f"\n回答: {result['answer']}")
        if result.get("sources"):
            print(f"\n来源: {len(result['sources'])} 个文档")

    elif args.command == "stats":
        stats = client.stats()
        print(f"文档数: {stats['document_count']}")
        print(f"向量块数: {stats['chunk_count']}")
        print(f"Embedding: {stats['embedding_model']}")

    elif args.command == "add":
        result = client.add_document(args.title, args.content)
        print(f"文档已添加，ID: {result['document_id']}")

    else:
        parser.print_help()
