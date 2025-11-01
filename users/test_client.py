#!/usr/bin/env python3
"""
最小化的 MCP 客户端脚本
可以连接到 Docker 中的 MCP proxy server 并进行聊天
"""
import asyncio
import os
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ============================================================================
# 配置
# ============================================================================
class Config:
    # OpenAI 配置
    api_key = "sk-c0d3d24b6eab4b9fbbf654c2a8817980"
    model = "qwen3-max"
    api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    # MCP Server 配置
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mcp_server_command = "bash"
    mcp_server_args = ["-c", f"cd {root_dir} && uv run python connect_v2.py"]


# ============================================================================
# 主程序
# ============================================================================
async def main():
    """主函数"""
    print("🔄 正在连接到 MCP 服务器...")
    
    # 创建服务器参数
    server_params = StdioServerParameters(
        command=Config.mcp_server_command,
        args=Config.mcp_server_args,
    )
    
    # 连接到 MCP 服务器
    async with stdio_client(server_params) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            
            # 获取工具列表
            tools_response = await session.list_tools()
            print(f"✅ 已连接！加载了 {len(tools_response.tools)} 个工具\n")
            
            # 创建 LLM
            llm = ChatOpenAI(
                model=Config.model,
                api_key=Config.api_key,
                base_url=Config.api_url,
            )
            
            # 转换 MCP 工具为 LangChain 格式
            lc_tools = []
            for tool in tools_response.tools:
                lc_tools.append({
                    'name': tool.name,
                    'description': tool.description or "No description",
                    'input_schema': tool.inputSchema
                })
            
            llm_with_tools = llm.bind_tools(lc_tools)
            
            # 聊天循环
            print("💬 开始聊天（输入 'q' 退出）\n")
            messages = []
            
            while True:
                try:
                    # 获取用户输入
                    user_input = input("User: ").strip()
                    if user_input.lower() in ['q', 'quit', 'exit']:
                        print("👋 再见！")
                        break
                    
                    if not user_input:
                        continue
                    
                    # 添加用户消息
                    messages.append(HumanMessage(content=user_input))
                    
                    # 调用 LLM
                    response = await llm_with_tools.ainvoke(messages)
                    messages.append(response)
                    
                    # 处理工具调用
                    while hasattr(response, 'tool_calls') and response.tool_calls:
                        for tool_call in response.tool_calls:
                            tool_name = tool_call['name']
                            tool_args = tool_call['args']
                            print(f"  🔧 调用工具: {tool_name}")
                            
                            # 调用 MCP 工具
                            try:
                                result = await session.call_tool(tool_name, arguments=tool_args)
                                # 提取文本内容
                                content_str = ""
                                if result.content:
                                    for item in result.content:
                                        if hasattr(item, 'text'):
                                            content_str += item.text
                                        else:
                                            content_str += str(item)
                                
                                messages.append(ToolMessage(
                                    content=content_str or "工具无返回",
                                    tool_call_id=tool_call['id']
                                ))
                            except Exception as e:
                                print(f"  ❌ 工具调用失败: {e}")
                                messages.append(ToolMessage(
                                    content=f"错误: {str(e)}",
                                    tool_call_id=tool_call['id']
                                ))
                        
                        # 再次调用 LLM 获取最终响应
                        response = await llm_with_tools.ainvoke(messages)
                        messages.append(response)
                    
                    # 显示助手响应
                    print(f"Assistant: {response.content}\n")
                    
                except EOFError:
                    print("\n👋 再见！")
                    break
                except Exception as e:
                    print(f"❌ 错误: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())

