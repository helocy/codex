from app.core.config import settings
from typing import List, Optional
import numpy as np
import json
import os


class EmbeddingService:
    CONFIG_FILE = "./config/embedding_config.json"

    def __init__(self):
        self.provider: str = "local"          # local | openai | doubao
        self.model_name: str = settings.EMBEDDING_MODEL
        self.api_key: Optional[str] = None
        self.base_url: Optional[str] = None
        self._local_model = None              # lazy load
        self._openai_client = None
        self._doubao_client = None

        # 加载保存的配置
        self._load_config()

    # ── 配置 ─────────────────────────────────────────────────────────────────
    def _load_config(self):
        """从文件加载配置"""
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.provider = config.get('provider', 'local')
                    self.model_name = config.get('model', settings.EMBEDDING_MODEL)
                    self.api_key = config.get('api_key')
                    self.base_url = config.get('base_url')
                    print(f"[Embedding] 加载配置: provider={self.provider}, model={self.model_name}")
        except Exception as e:
            print(f"[Embedding] 加载配置失败: {e}")

    def _save_config(self):
        """保存配置到文件"""
        try:
            os.makedirs(os.path.dirname(self.CONFIG_FILE), exist_ok=True)
            config = {
                'provider': self.provider,
                'model': self.model_name,
                'api_key': self.api_key,
                'base_url': self.base_url
            }
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"[Embedding] 配置已保存")
        except Exception as e:
            print(f"[Embedding] 保存配置失败: {e}")

    def configure(self, provider: str, model: str,
                  api_key: Optional[str] = None,
                  base_url: Optional[str] = None):
        self.provider = provider
        self.model_name = model
        self.api_key = api_key
        self.base_url = base_url
        self._local_model = None
        self._openai_client = None
        self._doubao_client = None
        # 保存配置
        self._save_config()

    def get_config(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model_name,
            "base_url": self.base_url or "",
        }

    # ── 公共接口 ──────────────────────────────────────────────────────────────
    def encode(self, texts: List[str]) -> np.ndarray:
        if self.provider == "local":
            return self._encode_local(texts)
        elif self.provider == "doubao":
            return np.array(self._encode_doubao(texts))
        return np.array(self._encode_openai(texts))

    def encode_single(self, text: str) -> np.ndarray:
        return self.encode([text])[0]

    # ── 本地模型 ──────────────────────────────────────────────────────────────
    def _encode_local(self, texts: List[str]) -> np.ndarray:
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer
            print(f"[Embedding] 加载本地模型: {self.model_name}")
            self._local_model = SentenceTransformer(self.model_name)
        return self._local_model.encode(texts, show_progress_bar=False)

    # ── 豆包 Embedding ────────────────────────────────────────────────────────
    def _encode_doubao_single(self, text: str) -> np.ndarray:
        """使用豆包 ARK API 对单条文本进行 embedding"""
        import requests

        if not self.api_key:
            raise ValueError("豆包嵌入模型需要配置 API Key")

        url = "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": self.model_name,
            "input": [{"type": "text", "text": text}]
        }

        response = requests.post(url, headers=headers, json=data, timeout=60)
        response.raise_for_status()

        result_data = response.json()
        embed_data = result_data.get("data", {})

        if isinstance(embed_data, dict) and "embedding" in embed_data:
            return np.array(embed_data["embedding"], dtype=np.float32)
        elif isinstance(embed_data, list) and embed_data:
            return np.array(embed_data[0].get("embedding", []), dtype=np.float32)

        raise ValueError(f"豆包 API 返回格式异常: {result_data}")

    def _encode_doubao(self, texts: List[str]) -> List[np.ndarray]:
        """并发调用豆包 API（multimodal API 不支持真正批量，改为并发请求）"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = [None] * len(texts)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self._encode_doubao_single, text): i
                       for i, text in enumerate(texts)}
            for future in as_completed(futures):
                idx = futures[future]
                results[idx] = future.result()
        return results

    # ── 云端 OpenAI 兼容接口 ─────────────────────────────────────────────────
    def _encode_openai(self, texts: List[str]) -> List[np.ndarray]:
        if self._openai_client is None:
            from openai import OpenAI
            if not self.api_key:
                raise ValueError("云端嵌入模型需要配置 API Key")
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._openai_client = OpenAI(**kwargs)

        response = self._openai_client.embeddings.create(
            model=self.model_name,
            input=texts,
        )
        # 按输入顺序排列
        ordered = sorted(response.data, key=lambda x: x.index)
        return [np.array(item.embedding, dtype=np.float32) for item in ordered]


# 全局实例
embedding_service = EmbeddingService()
