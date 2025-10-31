from typing import Literal
from langchain_core.tools import tool
from deploy.for_docker import DockerCommands, INSTALL, write_dockerfile

# 全局变量
server_paths_info = {}
server_env_info = {}
mappings = {}


@tool
def save_path_info(server_name: str, path: str) -> Literal['success', 'failed']:
    """ save the path info of the server """
    global server_paths_info
    if server_name not in server_paths_info:
        server_paths_info[server_name] = []
    server_paths_info[server_name].append(path)
    return 'success'

@tool
def add_mapping(host_path: str, docker_path: str) -> (Literal['success', 'failed'], str):
    """ add the mapping of the host path and the docker path """
    global mappings
    if host_path not in mappings:
        mappings[host_path] = docker_path
        return 'success', 'new mapping added'
    else:
        mappings[host_path] = docker_path
        return 'success', 'update exist mapping'


@tool
def install_package(package_name: str) -> Literal['success', 'failed']:
    """insert the package install command to the Dockerfile"""
    DockerCommands['install_commands'].append(INSTALL(package_name))
    return 'success'

@tool 
def rewrite_dockerfile() -> Literal['success', 'failed']:
    """rewrite the Dockerfile"""
    write_dockerfile(DockerCommands)
    return 'success'