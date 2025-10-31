import os
import shutil
from typing import Dict
import uuid

from .template import DOCKERFILE_TEMPLATE
from utils.configuration import Configuration
import logging

logger = logging.getLogger('shield_v2.deploy.for_docker')

DockerCommands = {
    'install_commands': [],
    'env_commands': [],
    'other_run_commands': [],
    'copy_commands': [],
}

docker_build_mappings = {}

class DockerCommand:
    def __init__(self, command: str, args: str):
        self.command = command
        self.args = args

    def __str__(self):
        return f"{self.command} {self.args}"

    def __repr__(self):
        return f"{self.command} {self.args}"

    @classmethod
    def from_command(cls, command: str) -> 'DockerCommand':
        return cls(command.split(' ')[0], ' '.join(command.split(' ')[1:]))

class COPY(DockerCommand):
    def __init__(self, source: str, destination: str):
        super().__init__('COPY', f"{source} {destination}")

class RUN(DockerCommand):
    def __init__(self, cmd: str = None, args: str = None):
        super().__init__('RUN', f"{cmd} {args}")

class ENV(DockerCommand):
    def __init__(self, name: str, value: str):
        super().__init__('ENV', f"{name}={value}")

class INSTALL(DockerCommand):
    def __init__(self, package_name: str):
        super().__init__('RUN', f"apt-get update && apt-get install -y {package_name} && rm -rf /var/lib/apt/lists/*")


def unique_file_name(dir_path:str, file_name:str) -> str:
    if os.path.exists(os.path.join(dir_path, file_name)):
        return unique_file_name(dir_path, f"{file_name}_{uuid.uuid4()}")
    return file_name

def make_dockerfile_commands(mappings: Dict[str, str], config:Configuration) -> bool:
    for host_path, docker_path in mappings.items():
        if os.path.exists(host_path):
            # 需要提供COPY指令，注意提供的host path需要是相对build路径的相对路径
            if os.path.isfile(host_path):
                # 文件直接平铺到docker构建目录中
                docker_build_name = unique_file_name(config.docker_build_path, os.path.basename(host_path))
                docker_build_path = os.path.join(config.docker_build_path, docker_build_name)
                shutil.copy(host_path, docker_build_path)
                docker_build_mappings[host_path] = docker_build_path
                DockerCommands['copy_commands'].append(COPY(docker_build_name, docker_path))
                logger.info(f"Copied file: {host_path} -> {docker_path}")
            elif os.path.isdir(host_path):
                # 保留最后一级目录，递归复制到docker构建目录中
                docker_build_name = unique_file_name(config.docker_build_path, os.path.basename(host_path))
                docker_build_path = os.path.join(config.docker_build_path, docker_build_name)
                shutil.copytree(host_path, docker_build_path)
                docker_build_mappings[host_path] = docker_build_path
                DockerCommands['copy_commands'].append(COPY(docker_build_name, docker_path))
                logger.info(f"Copied directory: {host_path} -> {docker_path}")
            else:
                logger.error(f"Unknown file type: {host_path}")
                return False

        else:
            # 路径不存在，创建目录或文件
            logger.warning(f"Path does not exist: {host_path}, will create directory or file: {docker_path}")
            if docker_path.endswith('/') or '.' not in os.path.basename(docker_path):
                DockerCommands['other_run_commands'].append(RUN(f"mkdir -p {docker_path}"))
            else:
                DockerCommands['other_run_commands'].append(RUN(f"touch {docker_path}"))
   
    return True

def write_dockerfile(config:Configuration) -> bool:
    try:
        with open(os.path.join(config.docker_build_path, 'Dockerfile'), 'w') as f:
            f.write(DOCKERFILE_TEMPLATE.format(
                install_commands='\n'.join([str(cmd) for cmd in DockerCommands['install_commands']]),
                env_commands='\n'.join([str(cmd) for cmd in DockerCommands['env_commands']]),
                other_run_commands='\n'.join([str(cmd) for cmd in DockerCommands['other_run_commands']]),
                copy_commands='\n'.join([str(cmd) for cmd in DockerCommands['copy_commands']]),
            ))
        return True
    except Exception as e:
        logger.error(f"Error writing Dockerfile: {e}")
        exit(1)




    