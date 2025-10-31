import os
import shutil
from typing import Any, Dict, Literal
from utils.utils import parse_mcp_server_info
from utils.configuration import Configuration
from .for_docker import make_dockerfile_commands, write_dockerfile

import logging
logger = logging.getLogger('shield_v2.deploy.server_info')

from agent_core.tools import (
    save_path_info, 
    server_env_info, 
    server_paths_info,
    add_mapping,
    mappings,
    )
from agent_core.llm import run_llm_loop
from deploy.prompt import *
import json
from pydantic import BaseModel, Field

class ParseServerInfoOutput(BaseModel):
    status: Literal['completed', 'failed', 'continue']
    message: str = Field(..., max_length=100, description="Brief description of current status or result")

class ConfigRewriteOutput(BaseModel):
    status: Literal['completed', 'failed', 'continue']
    server_config: Dict[Literal['servers', 'McpServers'], Any] = Field(..., description="The rewritten server config")



def save_env_info(server: str, env: dict):
    global server_env_info
    if server not in server_env_info:
        server_env_info[server] = {}
    server_env_info[server].update(env)

async def parse_info(config: Configuration):
    logger.info('start to parse server info')
    server_info = parse_mcp_server_info(config.mcp_config_path)
    for server, content in server_info.items():
        if 'env' in content:
            save_env_info(server, content['env'])

    response = await run_llm_loop(
        config={'configurable': {}},
        prompt_template=PARSE_SERVER_INFO,
        output_pydantic=ParseServerInfoOutput,
        format_args={'mcp_config_content': json.dumps(server_info)},
        tool_list=[save_path_info],
        max_iterations=10,
    )

    logger.info(f'succeed with content: {response["message"]}')
    logger.debug(f'server_paths_info: {server_paths_info}')


async def map_paths(config: Configuration):
    logger.info('start to map paths')
    response = await run_llm_loop(
        config={'configurable': {}},
        prompt_template=MAPPING,
        output_pydantic=ParseServerInfoOutput,
        format_args={'path_information': json.dumps(server_paths_info)},
        tool_list=[add_mapping],
        max_iterations=10,
    )
    logger.info(f'succeed with content: {response["message"]}')
    logger.debug(f'mappings: {mappings}')

async def rewrite_config(config: Configuration):
    logger.info('start to rewrite config')
    response = await run_llm_loop(
        config={'configurable': {}},
        prompt_template=CONFIG_REWRITE,
        output_pydantic=ConfigRewriteOutput,
        format_args={'mcp_config_content': str(parse_mcp_server_info(config.mcp_config_path)), 'path_mappings': str(mappings)},
        tool_list=[],
        max_iterations=2, # only one iteration is needed
    )

    logger.debug(f'succeed with config: {response["server_config"]}')
    logger.info('rewrite config succeed')

    assert type(response["server_config"]) == dict

    with open(config.mcp_config_path, 'r') as f:
        original_config = json.load(f)
        if 'servers' in response["server_config"] or 'McpServers' in response["server_config"]:
            original_config.update(response["server_config"])
        else:
            field = 'servers' if 'servers' in original_config else 'McpServers' if 'McpServers' in original_config else None
            assert field is not None, "No servers or McpServers field found in the original config"
            config_dict = {field: response["server_config"]}
            original_config.update(config_dict)
        file_path = os.path.join(config.docker_build_path, 'mcp.json')
        with open(file_path, 'w') as f2:
            json.dump(original_config, f2, indent=4)


async def parse_server_info(config: Configuration):
    await parse_info(config)
    await map_paths(config)
    await rewrite_config(config)


def build_docker_project(config:Configuration):
    # 拷贝必要的文件
    work_path = os.path.join(os.path.dirname(__file__), '..')
    work_path = os.path.abspath(work_path)
    pyproject_path = os.path.join(work_path, 'pyproject.toml')
    uv_lock_path = os.path.join(work_path, 'uv.lock')
    shield_mcp_path = os.path.join(work_path, 'shield_mcp')
    try:
        assert os.path.exists(pyproject_path), "pyproject.toml not found"
        assert os.path.exists(uv_lock_path), "uv.lock not found"
        assert os.path.exists(shield_mcp_path), "directory shield_mcp not found"
    except Exception as e:
        logger.error(f"Error checking necessary files: {e}")
        exit(1)

    # 拷贝必要文件
    shutil.copy(pyproject_path, os.path.join(config.docker_build_path, 'pyproject.toml'))
    shutil.copy(uv_lock_path, os.path.join(config.docker_build_path, 'uv.lock'))
    shutil.copytree(shield_mcp_path, os.path.join(config.docker_build_path, 'shield_mcp'))
    logger.debug(f'Copied pyproject.toml, uv.lock, shield_mcp to {config.docker_build_path}')
    # 撰写Dockerfile
    make_dockerfile_commands(mappings, config)
    write_dockerfile(config)
    logger.debug(f'Written Dockerfile to {config.docker_build_path}')