import json
from typing import Literal
import logging
    
logger = logging.getLogger('shield_v2.utils')

def parse_mcp_server_info(mcp_config_path: str) -> dict:
    try:
        with open(mcp_config_path, 'r') as f:
            mcp_config = json.load(f)
            server_field = 'servers' if 'servers' in mcp_config else 'McpServers' if 'McpServers' in mcp_config else None
            assert server_field is not None, "No MCP servers found in the .json file, need 'servers' or 'McpServers' field"
    except Exception as e:
        logger.error(f"Failed to read MCP config file: {e}")
        exit(1)
    return mcp_config[server_field]

