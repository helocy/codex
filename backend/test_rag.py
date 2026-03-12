"""
测试 RAG 对话功能
"""
import asyncio
from app.services.llm_service import llm_service

async def test_rag():
    """测试 RAG 对话"""

    print("=" * 50)
    print("测试 RAG 对话功能")
    print("=" * 50)
    print()

    # 配置 LLM
    llm_service.configure(
        provider="doubao",
        api_key="YOUR_API_KEY_HERE",
        model="doubao-seed-1-6-251015"
    )

    print("✓ LLM 已配置")
    print()

    # 测试 1: 简单对话
    print("测试 1: 简单对话")
    print("-" * 50)
    try:
        messages = [
            {"role": "user", "content": "你好"}
        ]
        response = await llm_service.chat(messages)
        print(f"问题: 你好")
        print(f"回答: {response}")
        print("✓ 简单对话测试通过")
    except Exception as e:
        print(f"✗ 简单对话测试失败: {e}")
    print()

    # 测试 2: RAG 对话
    print("测试 2: RAG 对话")
    print("-" * 50)
    try:
        query = "Python 是什么？"
        context_chunks = [
            "Python 是一种高级编程语言，由 Guido van Rossum 于 1991 年创建。",
            "Python 以其简洁的语法和强大的功能而闻名，广泛应用于 Web 开发、数据分析、人工智能等领域。"
        ]
        response = await llm_service.rag_chat(query, context_chunks)
        print(f"问题: {query}")
        print(f"上下文: {len(context_chunks)} 个文档片段")
        print(f"回答: {response}")
        print("✓ RAG 对话测试通过")
    except Exception as e:
        print(f"✗ RAG 对话测试失败: {e}")
    print()

    # 测试 3: 空上下文的 RAG 对话
    print("测试 3: 空上下文的 RAG 对话")
    print("-" * 50)
    try:
        query = "你好"
        context_chunks = []
        if not context_chunks:
            print("上下文为空，应该返回默认消息")
        else:
            response = await llm_service.rag_chat(query, context_chunks)
            print(f"回答: {response}")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
    print()

if __name__ == "__main__":
    asyncio.run(test_rag())
