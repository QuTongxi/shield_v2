import os
import shutil
import logging, sys
from rich.logging import RichHandler
import asyncio
import argparse

from utils.configuration import Configuration
from deploy.server_info import parse_server_info, build_docker_project


logging.basicConfig(
    level=logging.WARN,
    format='%(message)s',
    handlers=[RichHandler()]
)
logging.getLogger("shield_v2").setLevel(logging.DEBUG)
logger = logging.getLogger("shield_v2.main")

def parse_args():
    parser = argparse.ArgumentParser(description="shield_v2 runner")
    parser.add_argument('--config-yaml', default='config.yaml', help='Path to YAML to load Configuration from')
    return parser.parse_args()

async def run():
    args = parse_args()

    Configuration.load_from_yaml(args.config_yaml)
    logger.info(f"Using configuration: mcp_config_path={Configuration.mcp_config_path}, docker_build_path={Configuration.docker_build_path}")
    # 检查docker build path是否存在，如果存在就删除
    if os.path.exists(Configuration.docker_build_path):
        shutil.rmtree(Configuration.docker_build_path)
    os.makedirs(Configuration.docker_build_path, exist_ok=True)

    await parse_server_info(Configuration)
    build_docker_project(Configuration)

def main():
    asyncio.run(run())

if __name__ == '__main__':
    main()