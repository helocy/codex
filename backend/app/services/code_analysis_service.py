"""
代码分析服务 - 使用 LLM Agent 分析远端 SDK 源码
通过 function calling 驱动 SSH 工具，自主探索代码回答问题
"""
import json
import os
import re
import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from app.services.remote_code_service import remote_code_service
from app.core.config import settings

# 本地知识库目录：每次分析完成后自动保存 MD 文档
KNOWLEDGE_DIR = Path(__file__).parent.parent.parent / "knowledge"


def _load_knowledge(chip_models: List[str]) -> str:
    """加载本地积累的知识文档，注入 agent 上下文"""
    parts = []
    for chip in chip_models:
        chip_dir = KNOWLEDGE_DIR / chip.upper()
        if not chip_dir.exists():
            continue
        for md_file in sorted(chip_dir.glob("*.md"))[-10:]:  # 最多取最新 10 篇
            try:
                text = md_file.read_text(encoding="utf-8").strip()
                if text:
                    parts.append(f"### [{chip}] {md_file.stem}\n{text}")
            except Exception:
                pass
    if not parts:
        return ""
    return "【本地积累的历史分析知识（可直接参考，无需重复分析相同内容）】\n\n" + "\n\n---\n\n".join(parts)


def _save_knowledge(chip_models: List[str], query: str, result: str) -> None:
    """将本次分析结论保存为 MD 文档，供后续分析参考"""
    if not result or result.startswith("[代码分析]"):
        return
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # 从问题生成简短文件名（取前 30 个非特殊字符）
    safe_q = re.sub(r'[^\w\u4e00-\u9fff]+', '_', query)[:30].strip('_')
    for chip in chip_models:
        chip_dir = KNOWLEDGE_DIR / chip.upper()
        chip_dir.mkdir(parents=True, exist_ok=True)
        md_path = chip_dir / f"{timestamp}_{safe_q}.md"
        content = f"# {query}\n\n> 分析时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{result}\n"
        try:
            md_path.write_text(content, encoding="utf-8")
        except Exception:
            pass


def _get_code_analysis_client():
    """返回 (client, model, provider) 三元组。优先使用专用配置，否则 fallback 到主 LLM。"""
    provider = settings.CODE_ANALYSIS_LLM_PROVIDER
    api_key = settings.CODE_ANALYSIS_API_KEY
    model = settings.CODE_ANALYSIS_MODEL or "claude-sonnet-4-6"

    if provider == "anthropic" and api_key:
        import anthropic
        base_url = settings.CODE_ANALYSIS_BASE_URL
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return anthropic.Anthropic(**kwargs), model, "anthropic"

    # fallback: 返回 None，让 chat.py 传入主 LLM client
    return None, None, None


# Agent 可调用的工具定义
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_sdk_docs",
            "description": "列出指定芯片 SDK 的文档目录（PDF、Markdown），了解有哪些可参考文档",
            "parameters": {
                "type": "object",
                "properties": {
                    "chip_model": {"type": "string", "description": "芯片型号，如 RV1103B"},
                    "lang": {"type": "string", "enum": ["zh", "en"], "description": "文档语言，默认 zh"}
                },
                "required": ["chip_model"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出 SDK 某目录下的文件或子目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "chip_model": {"type": "string", "description": "芯片型号"},
                    "sub_path": {"type": "string", "description": "相对 SDK 根目录的路径，如 sysdrv/source/kernel/drivers/sound"},
                    "pattern": {"type": "string", "description": "文件名过滤，如 *.c 或 Kconfig"}
                },
                "required": ["chip_model", "sub_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep_code",
            "description": "在 SDK 源码中搜索关键词或模式，返回匹配行及文件路径。音频/PDM/I2S 相关驱动在 sysdrv/source/kernel/sound/soc/rockchip/ 目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "chip_model": {"type": "string", "description": "芯片型号"},
                    "pattern": {"type": "string", "description": "搜索关键词或正则"},
                    "sub_path": {"type": "string", "description": "搜索范围（相对 SDK 根），音频驱动用 sysdrv/source/kernel/sound/soc/rockchip，通用驱动用 sysdrv/source/kernel/drivers"},
                    "include": {"type": "string", "description": "文件类型过滤，如 *.c 或 *.h 或 Kconfig"}
                },
                "required": ["chip_model", "pattern", "sub_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取 SDK 中某个文件的内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "chip_model": {"type": "string", "description": "芯片型号"},
                    "file_path": {"type": "string", "description": "相对 SDK 根目录的文件路径"},
                    "start_line": {"type": "integer", "description": "起始行号，默认从头开始"},
                    "end_line": {"type": "integer", "description": "结束行号，0 表示读取前 12KB"}
                },
                "required": ["chip_model", "file_path"]
            }
        }
    }
]


def _execute_tool(name: str, args: dict) -> str:
    chip_model = args.get("chip_model", "")
    sdk_path = remote_code_service.find_sdk_path(chip_model)
    if not sdk_path:
        return f"错误：找不到芯片 {chip_model} 的 SDK，可用 SDK：{list(remote_code_service.list_sdks().keys())}"

    try:
        if name == "list_sdk_docs":
            lang = args.get("lang", "zh")
            result = remote_code_service.list_docs(sdk_path, lang)
            return result or f"{sdk_path}/docs/{lang} 目录为空或不存在"

        elif name == "list_files":
            full_path = f"{sdk_path}/{args['sub_path']}"
            pattern = args.get("pattern", "")
            result = remote_code_service.list_files(full_path, pattern)
            return result or f"目录 {full_path} 为空或不存在"

        elif name == "grep_code":
            full_path = f"{sdk_path}/{args['sub_path']}"
            result = remote_code_service.grep(
                pattern=args["pattern"],
                path=full_path,
                include=args.get("include", ""),
            )
            return result or f"未找到匹配 '{args['pattern']}' 的内容"

        elif name == "read_file":
            full_path = f"{sdk_path}/{args['file_path']}"
            result = remote_code_service.read_file(
                path=full_path,
                start_line=args.get("start_line", 1),
                end_line=args.get("end_line", 0),
            )
            return result or f"文件 {full_path} 为空或不存在"

    except Exception as e:
        return f"执行 {name} 出错：{e}"

    return "未知工具"


async def analyze_code(query: str, chip_models: List[str], llm_client=None, llm_model: str = None, rag_hints: str = "") -> str:
    """
    使用 LLM Agent 分析源码回答问题。
    优先使用 CODE_ANALYSIS_LLM_PROVIDER 配置的专用模型，否则使用传入的 llm_client。
    返回分析结论字符串，失败时返回 None。
    """
    # 优先使用专用代码分析 LLM
    dedicated_client, dedicated_model, dedicated_provider = _get_code_analysis_client()
    if dedicated_client:
        llm_client = dedicated_client
        llm_model = dedicated_model
        use_anthropic = (dedicated_provider == "anthropic")
    else:
        use_anthropic = False
    # 确认有对应 SDK；无芯片型号时从 workspace 根目录开始
    available = {}
    try:
        all_sdks = remote_code_service.list_sdks()
        if chip_models:
            for model in chip_models:
                path = remote_code_service.find_sdk_path(model)
                if path:
                    available[model] = path
            if not available:
                return f"[代码分析] 未找到以下芯片的 SDK：{chip_models}，可用 SDK：{list(all_sdks.keys())}"
        else:
            # 无指定芯片，使用 workspace 根目录（包含所有 SDK）
            available["workspace"] = settings.CODE_SDK_ROOT
    except Exception as e:
        return f"[代码分析] 连接远程服务器失败：{e}"

    # 预加载各芯片的文档列表，注入到初始消息，省去 agent 自己调 list_sdk_docs 的一轮
    doc_index_parts = []
    for model, path in available.items():
        try:
            docs = remote_code_service.list_docs(path)
            if docs:
                doc_index_parts.append(f"【{model} SDK 可用文档】\n{docs}")
        except Exception:
            pass
    doc_index_str = "\n\n".join(doc_index_parts) if doc_index_parts else "（文档列表获取失败）"

    system_prompt = f"""你是一名嵌入式 Linux 专家，负责通过分析 Rockchip SDK 文档和源码回答问题。

可用的 SDK 芯片型号：{list(available.keys())}

【分析策略（严格按顺序执行，不得跳过第一步）】：

第一步 — 必须先读文档（强制）：
  - 初始消息中已提供文档列表，立即根据问题关键词找最相关的文档
  - 用 read_file 读取 1~2 份最相关的文档全文，获取整体思路、关键配置项和文件路径线索
  - 禁止在读完文档前就开始 grep_code —— 文档里往往直接给出答案和示例代码
  - 文档通常在 docs/zh/ 或 docs/en/ 目录下

第二步 — 根据文档线索精准找源码：
  - 根据文档中提到的文件名、函数名、配置项，用 grep_code 定位具体代码
  - 不确定路径时，先用 list_files 探索 SDK 目录结构，再缩小范围

【grep 找不到时的通用回退策略（必须执行，禁止直接下结论）】：
  - 尝试换用同义词、缩写、相关术语再次 grep（功能名→接口名→寄存器名→枚举名）
  - 扩大搜索范围：先在子目录 grep，找不到再在父目录继续 grep
  - 用 list_files 浏览相关目录，从文件名推断实现位置，再 read_file 确认
  - 某功能可能集成在更通用的驱动/模块中，不是独立文件，需通过功能关键词而非功能名搜索
  - 只有穷举以上方法仍无结果时，才可声明「未在源码中找到相关实现」
  - ⚠️ 源码中未找到，绝不等于「芯片不支持该功能」——功能可能由文档/硬件层支持，或实现路径未被搜索到
    此时必须明确表述：「源码中未找到直接实现，功能是否支持请以官方文档/知识库为准」

第三步 — 读取关键代码并总结：
  - 用 read_file 读取文档或 grep 定位的关键代码文件
  - 综合文档描述 + 代码证据，给出明确结论

回答要求：
- 优先引用文档结论，再用代码佐证
- 明确说明结论来自哪份文档或哪个源码文件
- 给出文件路径和关键代码行
- 如果文档和代码都没找到，明确说明
- 中文回答"""

    # 加载本地积累的历史知识（如果有，直接注入，减少重复分析）
    local_knowledge = _load_knowledge(list(available.keys()))

    user_content_parts = [f"问题：{query}"]
    if rag_hints:
        user_content_parts.append(
            f"【知识库/文档已找到的关键线索（优先以此为搜索起点）】\n{rag_hints}"
        )
    if local_knowledge:
        user_content_parts.append(local_knowledge)
    user_content_parts.append(
        f"以下是 SDK 中已索引的文档列表，【若历史知识未覆盖本问题，第一步必须先从中找最相关的文档用 read_file 读取】，再分析源码：\n\n{doc_index_str}\n\n请严格按「读文档→找源码→总结」顺序分析，不得跳过读文档步骤。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n".join(user_content_parts)}
    ]

    # Anthropic 原生工具格式
    anthropic_tools = [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "input_schema": t["function"]["parameters"],
        }
        for t in TOOLS
    ]

    max_iterations = 8
    for i in range(max_iterations):
        try:
            if use_anthropic:
                # Anthropic SDK 格式（messages 不含 system，system 单独传）
                anth_messages = [m for m in messages if m["role"] != "system"]
                response = llm_client.messages.create(
                    model=llm_model,
                    system=system_prompt,
                    messages=anth_messages,
                    tools=anthropic_tools,
                    max_tokens=4096,
                )
                # 转换为统一格式处理
                text_blocks = [b.text for b in response.content if getattr(b, 'type', '') == 'text']
                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                final_text = "\n".join(text_blocks)

                if response.stop_reason == "end_turn" and not tool_use_blocks:
                    return final_text

                if tool_use_blocks:
                    # 记录 assistant 消息
                    messages.append({"role": "assistant", "content": response.content})
                    tool_results = []
                    for tb in tool_use_blocks:
                        tool_result = _execute_tool(tb.name, tb.input)
                        print(f"[CodeAnalysis] tool={tb.name} chip={tb.input.get('chip_model')} -> {len(tool_result)} chars", flush=True)
                        limit = 4000 if tb.name == "read_file" else 2500
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "content": tool_result[:limit],
                        })
                    messages.append({"role": "user", "content": tool_results})
                else:
                    return final_text or ""
            else:
                # OpenAI 兼容格式
                response = llm_client.chat.completions.create(
                    model=llm_model,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=2000,
                )
                msg = response.choices[0].message

                if msg.content and not msg.tool_calls:
                    return msg.content

                if msg.tool_calls:
                    messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
                        {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in msg.tool_calls
                    ]})
                    for tc in msg.tool_calls:
                        try:
                            args = json.loads(tc.function.arguments)
                        except Exception:
                            args = {}
                        tool_result = _execute_tool(tc.function.name, args)
                        print(f"[CodeAnalysis] tool={tc.function.name} chip={args.get('chip_model')} -> {len(tool_result)} chars", flush=True)
                        limit = 4000 if tc.function.name == "read_file" else 2500
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_result[:limit],
                        })
                else:
                    break

        except Exception as e:
            return f"[代码分析] LLM 调用失败：{e}"

    # 超过最大迭代，要求 LLM 总结
    if use_anthropic:
        anth_messages = [m for m in messages if m["role"] != "system"]
        anth_messages.append({"role": "user", "content": "请根据以上搜索结果，给出最终结论。"})
        try:
            response = llm_client.messages.create(
                model=llm_model,
                system=system_prompt,
                messages=anth_messages,
                max_tokens=1000,
            )
            return "".join(b.text for b in response.content if hasattr(b, 'text'))
        except Exception as e:
            return f"[代码分析] 总结失败：{e}"
    else:
        messages.append({"role": "user", "content": "请根据以上搜索结果，给出最终结论。"})
        try:
            response = llm_client.chat.completions.create(
                model=llm_model,
                messages=messages,
                temperature=0.1,
                max_tokens=1000,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[代码分析] 总结失败：{e}"


def analyze_code_sync(query: str, chip_models: List[str], llm_client=None, llm_model: str = None, rag_hints: str = "") -> str:
    """analyze_code 的同步包装，供 asyncio.to_thread 在线程池中调用"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(analyze_code(query, chip_models, llm_client, llm_model, rag_hints))
        # 分析完成后，将结论保存为本地知识文档
        _save_knowledge(chip_models, query, result)
        return result
    finally:
        loop.close()
