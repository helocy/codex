"""
LLM 服务 - 支持多种大模型提供商
"""
from typing import List, Dict, Optional
import httpx
from openai import OpenAI
from app.core.config import settings


class LLMService:
    """大语言模型服务"""

    def __init__(self):
        self.provider = None
        self.client = None
        self.model = None

    def configure(self, provider: str, api_key: Optional[str] = None,
                  base_url: Optional[str] = None, model: Optional[str] = None):
        """配置 LLM 提供商"""
        self.provider = provider
        self.model = model

        if provider == "ollama":
            # Ollama 本地模型
            self.client = OpenAI(
                base_url=base_url or "http://localhost:11434/v1",
                api_key="ollama"  # Ollama 不需要真实 API key
            )
            self.model = model or "llama3"

        elif provider == "openai":
            # OpenAI API
            self.client = OpenAI(api_key=api_key)
            self.model = model or "gpt-3.5-turbo"

        elif provider == "doubao":
            # 豆包 API (字节跳动) - 使用标准 chat.completions 接口
            self.client = OpenAI(
                base_url=base_url or "https://ark.cn-beijing.volces.com/api/v3",
                api_key=api_key
            )
            # 豆包的模型 ID，用户可以在设置中自定义
            self.model = model or "doubao-pro-4k"

        elif provider == "qwen":
            # 通义千问 API (阿里)
            self.client = OpenAI(
                base_url=base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=api_key
            )
            self.model = model or "qwen-turbo"

        else:
            # 通用自定义 API (支持任意 OpenAI 兼容的大模型)
            if not base_url:
                raise ValueError("自定义 API 需要提供 Base URL")
            self.client = OpenAI(
                base_url=base_url,
                api_key=api_key or "dummy-key"
            )
            self.model = model or "gpt-3.5-turbo"

    async def chat(self, messages: List[Dict[str, str]],
                   temperature: float = 0.7,
                   max_tokens: int = 2000) -> str:
        """
        发送聊天请求

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            模型回复内容
        """
        if not self.client:
            raise ValueError("LLM 未配置，请先调用 configure()")

        try:
            # 豆包和其他提供商都使用标准的 chat.completions 接口
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"LLM 调用失败: {str(e)}")

    async def rag_chat(self, query: str, context_chunks: List[str],
                       history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        RAG 对话 - 基于检索到的上下文回答问题，支持多轮对话历史

        Args:
            query: 用户问题
            context_chunks: 检索到的相关文本片段
            history: 历史对话 [{"role": "user/assistant", "content": "..."}]

        Returns:
            基于上下文的回答
        """
        context = "\n\n---\n\n".join([f"[片段 {i+1}]\n{chunk}"
                                      for i, chunk in enumerate(context_chunks)])

        system_prompt = """你是一个智能助手，基于用户的个人知识库回答问题。

规则：
1. 只依据下方「参考文档」中的内容作答，不要编造或猜测文档之外的信息。
2. 每个片段开头标注了「来源：文档名」。如果问题涉及特定芯片/产品型号，只能引用该型号对应的文档内容，不得用其他型号的文档推断或替代回答。
3. 如果参考文档中没有找到该型号的直接证据，请明确说"在已上传的文档中未找到该型号的相关信息"，不要强行作答。
4. 回答要准确、有条理，可适当引用来源文档名。
5. 结合对话历史保持上下文连贯。"""

        user_prompt = f"""参考文档：
{context}

问题：{query}"""

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        # 插入历史（最多保留最近 6 轮，避免 token 超限）
        if history:
            messages.extend(history[-12:])

        messages.append({"role": "user", "content": user_prompt})

        return await self.chat(messages)

    async def plain_chat(self, query: str,
                         history: Optional[List[Dict[str, str]]] = None) -> str:
        """普通对话（无 RAG），支持多轮历史"""
        messages: List[Dict[str, str]] = []
        if history:
            messages.extend(history[-12:])
        messages.append({"role": "user", "content": query})
        return await self.chat(messages)

    async def web_search_chat(self, query: str, web_context: str,
                             history: Optional[List[Dict[str, str]]] = None) -> str:
        """网络搜索对话 - 基于网络搜索结果回答问题"""
        system_prompt = """你是一个智能助手，基于网络搜索结果回答用户的问题。

规则：
1. 必须使用下方提供的网络搜索结果来回答问题。
2. 如果搜索结果与问题无关，请如实说明"没有找到相关信息"。
3. 对于实时性信息（如新闻、天气、股票等），必须基于搜索结果回答。
4. 不要编造信息，所有回答必须有搜索结果作为依据。
5. 回答要准确标注信息来源（搜索结果的标题/URL）。
6. 结合对话历史保持上下文连贯。"""

        user_prompt = f"""网络搜索结果：
{web_context}

用户问题：{query}

请根据以上搜索结果回答问题："""

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        if history:
            messages.extend(history[-12:])

        messages.append({"role": "user", "content": user_prompt})

        return await self.chat(messages)

    async def rag_chat_with_web(self, query: str, combined_context: str,
                                history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        RAG + 网络搜索混合对话 - 结合知识库和网络搜索结果回答问题

        Args:
            query: 用户问题
            combined_context: 组合上下文（知识库 + 网络搜索）
            history: 历史对话
        """
        system_prompt = """你是一个智能助手，结合用户的个人知识库和网络搜索结果回答问题。

【重要】回答优先级规则：
1. **知识库优先**：必须首先并且主要使用个人知识库（【知识库文档】标记的内容）来回答问题，这是最可信的来源。
2. **网络补充**：只有当知识库中没有相关信息时，才使用【网络搜索结果】作为补充。
3. **注明来源**：回答时必须清楚标注每条信息的来源是知识库还是网络。
4. **诚实原则**：如果知识库和网络都没有相关信息，请明确说明在知识库和网络中都没有找到相关内容。
5. **时效性**：对于实时信息（新闻、天气、股票等），可以以网络搜索结果为准，但仍要说明来源。
6. **上下文连贯**：结合对话历史保持连贯性。"""

        user_prompt = f"""请根据以下参考资料回答用户的问题：

{combined_context}

问题：{query}"""

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        if history:
            messages.extend(history[-12:])

        messages.append({"role": "user", "content": user_prompt})

        return await self.chat(messages)

    async def comparison_chat(self, query: str, grouped_context: str,
                              history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        对比类对话 - 专门用于对比两个或多个实体的查询

        Args:
            query: 用户问题（对比查询）
            grouped_context: 按文档分组的上下文
            history: 历史对话
        """
        system_prompt = """你是一个智能助手，专门帮助用户对比分析不同产品、技术或概念。

【重要】对比分析规则：
1. **全面性**：必须基于所有提供的文档进行对比，不要遗漏任何一个实体。
2. **结构化**：使用表格或分点对比的方式，清晰展示各实体的异同。
3. **准确性**：只使用文档中明确提到的信息，不要编造或推测。
4. **标注来源**：对于每个关键信息，标注来自哪个文档。
5. **诚实原则**：如果某个文档中缺少某项信息，明确说明"文档中未提及"。
6. **对比维度**：尽可能从多个维度进行对比（如性能、功能、规格、应用场景等）。"""

        user_prompt = f"""参考文档（已按文档分组）：

{grouped_context}

对比问题：{query}

请基于以上文档进行全面对比分析："""

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        if history:
            messages.extend(history[-12:])

        messages.append({"role": "user", "content": user_prompt})

        return await self.chat(messages)

    async def rag_chat_with_original(self, query: str, full_context: str,
                                     history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        RAG 对话（包含原始文档）- 基于知识库和原始文档回答问题

        Args:
            query: 用户问题
            full_context: 完整上下文（包含知识库文档和原始文档）
            history: 历史对话
        """
        system_prompt = """你是一个智能助手，基于用户的个人知识库和原始文档回答问题。

【重要】回答规则：
1. **优先使用原始文档**：如果提供了【原始文档】标记的内容，这是最完整、最权威的信息来源，应优先参考。
2. **知识库作为补充**：【知识库文档】中的内容是从原始文档中提取的片段，可以作为快速定位和补充。
3. **准确性**：只依据提供的文档内容作答，不要编造或猜测。
4. **诚实原则**：如果文档中没有足够信息，请明确说明"文档中没有找到相关信息"。
5. **必须说明原始文档使用情况**：
   - 如果找到了原始文档，必须在回答开头说明"✓ 已找到原始文档：[文档名]"
   - 如果参考了原始文档的具体内容，必须说明参考了哪些部分（如页码、章节等）
   - 如果没有找到原始文档，必须说明"✗ 未找到原始文档，仅使用知识库片段"
6. **上下文连贯**：结合对话历史保持连贯性。

【回答格式要求】：
第一段：说明原始文档查找和使用情况
第二段开始：具体回答用户问题"""

        user_prompt = f"""参考资料：

{full_context}

问题：{query}

请基于以上资料回答问题："""

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        if history:
            messages.extend(history[-12:])

        messages.append({"role": "user", "content": user_prompt})

        return await self.chat(messages)


# 全局 LLM 服务实例
llm_service = LLMService()
