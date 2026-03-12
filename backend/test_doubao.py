"""
测试豆包 API 连接
"""
import asyncio
from openai import OpenAI

async def test_doubao():
    """测试豆包 API"""

    # 配置
    api_key = "YOUR_API_KEY_HERE"
    base_url = "https://ark.cn-beijing.volces.com/api/v3"
    model = "doubao-seed-1-6-251015"

    print("=" * 50)
    print("测试豆包 API 连接")
    print("=" * 50)
    print(f"Base URL: {base_url}")
    print(f"Model: {model}")
    print(f"API Key: {api_key[:20]}...")
    print()

    try:
        # 创建客户端
        client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )

        print("✓ 客户端创建成功")
        print()

        # 测试简单对话
        print("发送测试消息: '你好，请介绍一下你自己'")
        print()

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "你好，请介绍一下你自己"}
            ],
            temperature=0.7,
            max_tokens=500
        )

        answer = response.choices[0].message.content

        print("✓ API 调用成功!")
        print()
        print("回复内容:")
        print("-" * 50)
        print(answer)
        print("-" * 50)
        print()
        print("✓ 豆包 API 工作正常!")

    except Exception as e:
        print(f"✗ 错误: {type(e).__name__}")
        print(f"✗ 详细信息: {str(e)}")
        print()
        print("可能的原因:")
        print("1. API Key 不正确")
        print("2. 模型 ID 不正确")
        print("3. 网络连接问题")
        print("4. 豆包服务暂时不可用")

if __name__ == "__main__":
    asyncio.run(test_doubao())
