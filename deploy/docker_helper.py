import threading
from typing import Callable, Optional, Union
import docker
import subprocess
import os
import logging

from docker.models.containers import Container

work_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(work_dir, 'docker_helper.log')

logger = logging.getLogger('shield_v2.deploy.docker_helper')
handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

class DockerInfo:
    client: docker.DockerClient = None
    image_name: str = None
    container_name: str = None

    @staticmethod
    def from_config(config) -> 'DockerInfo':
        """Create New DockerInfo from config"""
        available_keys = DockerInfo.__annotations__.keys()
        args = {key: config.get(key, getattr(DockerInfo, key)) for key in available_keys}
        return DockerInfo(**args)

    @staticmethod
    def update(kwargs: dict) -> None:
        """Update DockerInfo with kwargs"""
        for key, value in kwargs.items():
            setattr(DockerInfo, key, value)

def build_all(
    client: docker.DockerClient,
    image_name: str,
    dockerfile: str,
    build_path: str,
    force_rebuild: bool = False,
) -> (Union[bool, Container], str):
    """Build a Docker image"""
    debug_info = ""
    DockerInfo.client = client
    if force_rebuild:
        images = client.images.list(name=image_name)
        if images:
            client.images.remove(image_name, force=True)
            debug_info += f"Removed existing image {image_name}\n"
   
    try:
        client.images.build(
            path=os.path.abspath(build_path),
            tag=image_name,
            dockerfile=dockerfile,
            rm=True,
        )
        debug_info += f"Built image {image_name}\n"
        DockerInfo.image_name = image_name
    except Exception as e:
        debug_info += f"Failed to build image {image_name}: {e}\n build args: path={build_path}, dockerfile={dockerfile}, image_name={image_name}"
        return False, debug_info

    try:
        container = client.containers.run(
            image=image_name,
            stdin_open=True,
            detach=True,
            remove=True,
        )
        debug_info += f"Created container {container.name}\n"
        DockerInfo.container_name = container.name
        return container, debug_info
    except Exception as e:
        debug_info += f"Failed to create container {image_name}: {e}\n"
        return False, debug_info

def clean_all(docker_info: DockerInfo = None) -> (bool, str):
    """Cleanup all Docker resources - find and remove all containers using the specified image"""
    image_name = docker_info.image_name if docker_info else DockerInfo.image_name
    client = docker_info.client if docker_info else DockerInfo.client
    debug_info = ""
    
    try:
        # 查找所有使用该镜像的容器
        containers = client.containers.list(all=True, filters={'ancestor': image_name})    
        if containers:            
            # 停止并删除所有容器
            for container in containers:
                container.remove(force=True)
                debug_info += f"Removed container {container.name} ({container.short_id})\n"
        else:
            debug_info += f"No containers found using image {image_name}\n"
        
        # 删除镜像
        client.images.remove(image_name, force=True)
        debug_info += f"Removed image {image_name}\n"
        
    except Exception as e:
        debug_info += f"Failed to cleanup Docker resources: {e}\n"
        return False, debug_info
    
    return True, debug_info

def run_immediate_command(docker_info: DockerInfo = None, command: str | list[str] = None) -> (bool, str):
    """同步执行命令，会阻塞当前线程，仅用于简单迅速的命令执行"""
    container: Container = docker_info.container if docker_info else DockerInfo.container
    try:
        code, output = container.exec_run(command)
        assert code == 0, f"Command failed with code {code}: {output}"
        return True, output
    except Exception as e:
        return False, str(e)

def run_stream_command(
    docker_info: DockerInfo = None, 
    command: str | list[str] = None,
    handler: Callable = None,
    ) -> int:
    client: docker.DockerClient = docker_info.client if docker_info else DockerInfo.client
    container_name = docker_info.container_name if docker_info else DockerInfo.container_name
    container = client.containers.get(container_name)
    resp = client.api.exec_create(
        container = container.id,
        cmd = command,
        stdin = True, # 必须为true，否则mcp会认为通信结束了。
    )
    exec_id = resp['Id']
    exec_stream = client.api.exec_start(exec_id, stream=True, demux=True)

    for (_, chunk) in exec_stream:
        if chunk and handler:
            handler(chunk.decode('utf-8'))
        
        
        
    exit_code = client.api.exec_inspect(exec_id)['ExitCode']
    return exit_code

