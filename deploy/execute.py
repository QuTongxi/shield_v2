import logging
import os
import docker

from typing import Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from utils.configuration import Configuration
from agent_core.llm import run_llm_loop
from pydantic import BaseModel, Field

from .docker_helper import build_all, clean_all, run_stream_command
from .for_docker import install_package, insert_run_command, write_to_dockerfile
from .prompt import DOCKERFILE_DEBUG

logger = logging.getLogger('shield_v2.deploy.execute')
logger.setLevel(logging.DEBUG)

class ExecuteOutput(BaseModel):
    status: Literal['completed', 'failed', 'continue']
    message: str = Field(..., max_length=100, description="Brief description of current status or result")


def build_debug_container() -> (bool, str):
    """
    Build the container and run the command to test the Dockerfile.
    Returns:
        bool: True if the container is built and the command is run successfully, False otherwise.
        str: The logs of the container.
    """
    client = docker.from_env()
    resp, info = build_all(
        client,
        image_name = Configuration.docker_image_name,
        dockerfile = 'Dockerfile',
        build_path = Configuration.docker_build_path,
        force_rebuild = True,
    )
    if type(resp) == bool:
        return False, f'fail to build the image: {info}'

    container = resp
    running_logs = ""
    def testing_handler(content: str):
        nonlocal running_logs
        running_logs += content
        logger.info(f'GET LOGS: {running_logs}')
    
    exit_code = run_stream_command(
        command = Configuration.default_debug_cmd,
        handler = testing_handler,
    )
    clean_all()
    return exit_code == 0, running_logs


@tool
def build_container() -> (bool, str):
    """
    Build the container and run the command to test the Dockerfile.
    Returns:
        bool: True if the container is built and the command is run successfully, False otherwise.
        str: The logs of the container.
    """
    return build_debug_container()

@tool
def read_dockerfile() -> str:
    """
    Read the content of the Dockerfile.
    Returns:
        str: The content of the Dockerfile.
    """
    with open(os.path.join(Configuration.docker_build_path, 'Dockerfile'), 'r') as f:
        return f.read()

async def try_execute_dockerfile(config: RunnableConfig):
    configuration = Configuration.from_runnable_config(config)
    flag, logs = build_debug_container()
    if flag:
        return {'status': 'completed', 'message': ''}

    logger.info('Errors detected, trying to fix the Dockerfile...')
    resp = await run_llm_loop(
        config = config,
        prompt_template=DOCKERFILE_DEBUG,
        output_pydantic=ExecuteOutput,
        format_args={
            'error_information': logs,
            'command_information': Configuration.default_debug_cmd,
        },
        tool_list=[
            read_dockerfile,
            install_package,
            insert_run_command,
            write_to_dockerfile,
            build_container,
        ]
    )

    if resp['status'] == 'completed':
        logger.info(f'Dockerfile fixed successfully, notes:\n{resp["message"]}')
        return resp
    elif resp['status'] == 'failed':
        logger.error(f'Failed to fix the Dockerfile: {resp["message"]}')
        exit(1)
    else:
        raise
    
