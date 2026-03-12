from typing import List, Dict, Optional
import requests
import json
import os


class WebSearchService:
    """网络搜索服务 - 支持多种搜索 API"""

    def __init__(self):
        self.provider = os.environ.get("WEB_SEARCH_PROVIDER", "duckduckgo")
        self.api_key = os.environ.get("SEARCH_API_KEY", "")

    def search(self, query: str, num_results: int = 5) -> List[Dict]:
        """执行网络搜索"""
        if self.provider == "duckduckgo":
            return self._search_duckduckgo(query, num_results)
        elif self.provider == "serper":
            return self._search_serper(query, num_results)
        elif self.provider == "tavily":
            return self._search_tavily(query, num_results)
        else:
            return self._search_duckduckgo(query, num_results)

    def _search_duckduckgo(self, query: str, num_results: int = 5) -> List[Dict]:
        """使用 DuckDuckGo HTML 搜索（免费，无需 API Key）"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            url = "https://html.duckduckgo.com/html/"
            data = {"q": query, "b": "", "kl": "cn-zh"}

            response = requests.post(url, data=data, headers=headers, timeout=10)
            response.raise_for_status()

            results = []
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")

            for result in soup.select(".result")[:num_results]:
                title_elem = result.select_one(".result__title")
                link_elem = result.select_one(".result__url")
                snippet_elem = result.select_one(".result__snippet")

                if title_elem and link_elem:
                    # 获取实际 URL（从 href 属性）
                    url = link_elem.get("href", "")
                    if url:
                        results.append({
                            "title": title_elem.get_text(strip=True),
                            "url": url,
                            "snippet": snippet_elem.get_text(strip=True) if snippet_elem else ""
                        })

            return results
        except Exception as e:
            print(f"[WebSearch] DuckDuckGo search error: {e}")
            return []

    def _search_serper(self, query: str, num_results: int = 5) -> List[Dict]:
        """使用 Serper API（需要 API Key）"""
        if not self.api_key:
            return []

        try:
            url = "https://google.serper.dev/search"
            headers = {
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json"
            }
            data = {"q": query, "num": num_results}

            response = requests.post(url, json=data, headers=headers, timeout=10)
            response.raise_for_status()

            results = []
            for item in response.json().get("organic", [])[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", "")
                })

            return results
        except Exception as e:
            print(f"[WebSearch] Serper search error: {e}")
            return []

    def _search_tavily(self, query: str, num_results: int = 5) -> List[Dict]:
        """使用 Tavily API（需要 API Key）"""
        if not self.api_key:
            return []

        try:
            url = "https://api.tavily.com/search"
            data = {
                "api_key": self.api_key,
                "query": query,
                "max_results": num_results
            }

            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()

            results = []
            for item in response.json().get("results", [])[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", "")
                })

            return results
        except Exception as e:
            print(f"[WebSearch] Tavily search error: {e}")
            return []


# 全局实例
web_search_service = WebSearchService()
