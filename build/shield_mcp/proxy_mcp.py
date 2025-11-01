# 
# to use this server, run python proxy_mcp.py --mcp mcp.json
# 

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Optional
import json

import mcp.server.stdio
import mcp.types as types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

import logging
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("mcp").setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.WARNING)
log = logging.getLogger('shield_v2.shield_mcp.proxy_mcp')
log.setLevel(logging.INFO)

import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--mcp', type=str, default='mcp.json')
parser.add_argument('--debug', action='store_true', help='Debug mode: connect to all servers and exit')
args = parser.parse_args()

# ============================================================================
# MCP Client 部分 
# ============================================================================

def handle_errors(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            log.error(f"Error in {func.__name__}: {e}")
            exit(1)
    return wrapper

class McpClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.server_name: Optional[str] = None
        
    @handle_errors
    async def connect_to_server(self, server_name: str, **kwargs):
        """
        Connect to a MCP server using local json config files.
        TODO: Add support for HTTP transport.
        """
        start_args = {k: v for k, v in kwargs.items() if k != "disabled"}
        server_params = StdioServerParameters(**start_args)   
        
        # connect to the server
        self.server_name = server_name
        log.debug(f"Connecting to stdio server {server_name} with params {server_params}")

        self.transport_context = stdio_client(server_params)
        streams = await self.transport_context.__aenter__()
        self.session_context = ClientSession(streams[0],streams[1])
        self.session = await self.session_context.__aenter__()
        await self.session.initialize()
        
        # list tools
        response = await self.session.list_tools()       
        tools = response.tools
        log.debug(f"\nConnected to server with tools: {[tool.name for tool in tools]}")
        log.info(f'Connect to server {server_name} successfully!')
    
    @handle_errors
    async def close(self):
        """Close the client session."""
        if self.session_context:
            await self.session_context.__aexit__(None, None, None)
        if self.transport_context:
            await self.transport_context.__aexit__(None, None, None)
        self.session = None

class McpHost:
    def __init__(self):
        self.mcp_clients: Optional[dict[str, McpClient]] = None
        self.start_args: dict[str, Any] = {}

    def get_server_names(self):
        return list(self.mcp_clients.keys())

    def get_start_command(self, server_name: str):
        return self.start_args[server_name]
    
    @handle_errors
    async def load_mcp_config(self, config_path: str):
        """Load the configuration file."""
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        self.mcp_clients = {}
        field = "McpServers" if "McpServers" in config else "servers" if "servers" in config else None
        if field is None:
            log.error("No MCP servers found in json file, need 'McpServers' or 'servers' field")
            raise
        for server_name, server_config in config[field].items():
            log.debug(f"Connecting to server {server_name} with config {server_config}")
            mcp_client = McpClient()
            self.start_args[server_name] = server_config
            await mcp_client.connect_to_server(server_name, **server_config)
            self.mcp_clients[server_name] = mcp_client

    async def get_tools_list(self):
        """Get the tools list from all MCP servers."""
        tools_list = []
        for mcp_client in self.mcp_clients.values():
            response = await mcp_client.session.list_tools()
            for tool in response.tools:
                tool.name = f"{mcp_client.server_name}-{tool.name}"

            tools_list.extend(response.tools)
        return tools_list

    async def call_tool(self, name: str, args: dict):
        """Call a tool from the MCP server."""
        server_name, tool_name = name.split('-', 1)
        return await self.mcp_clients[server_name].session.call_tool(tool_name, args)

    async def close(self):
        all_clients = list(self.mcp_clients.values())
        for mcp_client in all_clients[::-1]:
            await mcp_client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# ============================================================================
# MCP Proxy Server 部分
# ============================================================================

@asynccontextmanager
async def server_lifespan(_server: Server) -> AsyncIterator[object]:
    mcp_host = McpHost()
    await mcp_host.load_mcp_config(args.mcp)
    log.debug("Connected to MCP servers")

    try:
        yield {'mcp_host': mcp_host}
    finally:
        await mcp_host.close()

server = Server("proxy-server", lifespan=server_lifespan)

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    mcp_host = server.request_context.lifespan_context['mcp_host']
    return await mcp_host.get_tools_list()

@server.call_tool()
async def call_tool(tool_name: str, arguments: dict) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    mcp_host = server.request_context.lifespan_context['mcp_host']
    result = await mcp_host.call_tool(tool_name, arguments)
    return result.content

@server.list_prompts()
async def handle_list_prompts(request: types.ListPromptsRequest) -> types.ListPromptsResult:
    raise NotImplementedError("List prompts is not implemented")

@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    raise NotImplementedError("Get prompt is not implemented")

@server.list_resource_templates()
async def handle_list_resource_templates() -> list[types.ResourceTemplate]:
    raise NotImplementedError("List resource templates is not implemented")





async def run():
    """Run the proxy server."""
    async with mcp.server.stdio.stdio_server() as session:
        await server.run(
            session[0],
            session[1],
            InitializationOptions(
                server_name="proxy-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

async def debug_connect():
    """Debug mode: connect to all MCP servers and exit."""
    log.info("Running in debug mode")
    print('Debug mode: connecting to all MCP servers...')
    
    mcp_host = McpHost()
    await mcp_host.load_mcp_config(args.mcp)
    
    server_names = mcp_host.get_server_names()
    print(f'Successfully connected to {len(server_names)} server(s): {", ".join(server_names)}')
    
    # 清理资源
    await mcp_host.close()
    print('All servers disconnected. Exiting.')

if __name__ == "__main__":
    if args.debug:
        log.info("Debug mode is not used for release version")
        asyncio.run(debug_connect())
    else:
        log.info("Starting proxy server")
        print('starting proxy server')
        asyncio.run(run())

