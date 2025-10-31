import docker
import subprocess
import sys
import os
import logging
import argparse
import threading

# 文件现在在主文件夹下，项目根目录就是当前文件所在目录
_project_root = os.path.abspath(os.path.dirname(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from utils.configuration import Configuration

logger = logging.getLogger('shield_v2.connect')


def build_docker_image(client: docker.DockerClient, config: Configuration, force_rebuild: bool = False) -> None:
    """构建 Docker 镜像"""
    if force_rebuild:
        logger.info(f"Removing existing image {config.docker_image_name}...")
        client.images.remove(config.docker_image_name, force=True)
    else:
        try:
            client.images.get(config.docker_image_name)
            logger.debug(f"Docker image {config.docker_image_name} already exists")
            return
        except docker.errors.ImageNotFound:
            pass
    
    logger.info(f"Building Docker image {config.docker_image_name}...")
    abs_build_path = os.path.abspath(config.docker_build_path)
    dockerfile_path = os.path.join(abs_build_path, 'Dockerfile')
    
    if not os.path.exists(dockerfile_path):
        raise FileNotFoundError(f"Dockerfile not found at {dockerfile_path}")
    
    client.images.build(
        path=abs_build_path,
        tag=config.docker_image_name,
        dockerfile='Dockerfile',
        rm=True,
    )
    logger.info(f"Docker image {config.docker_image_name} built successfully")


def get_or_create_container(client: docker.DockerClient, config: Configuration, force_recreate: bool = False) -> docker.models.containers.Container:
    """获取或创建 Docker 容器"""
    container_name = f"{config.docker_image_name.replace(':', '-')}-container"
    
    if force_recreate:
        try:
            existing_container = client.containers.get(container_name)
            logger.info(f"Removing existing container {container_name}...")
            if existing_container.status == 'running':
                existing_container.stop()
            existing_container.remove()
        except docker.errors.NotFound:
            pass
    else:
        try:
            container = client.containers.get(container_name)
            if container.status != 'running':
                logger.info(f"Starting existing container {container_name}...")
                container.start()
            else:
                logger.debug(f"Container {container_name} is already running")
            return container
        except docker.errors.NotFound:
            pass
    
    logger.info(f"Creating new container {container_name}...")
    return client.containers.run(
        config.docker_image_name,
        name=container_name,
        stdin_open=True,
        detach=True,
        remove=False,
    )


def cleanup_container(container: docker.models.containers.Container) -> None:
    """停止并删除容器"""
    container.reload()
    if container.status == 'running':
        logger.info(f"Stopping container {container.name}...")
        container.stop()
    logger.info(f"Removing container {container.name}...")
    container.remove()


def run_command_in_container(config: Configuration, command: str | list[str], timeout: float) -> bool | str:
    """构建镜像和容器，运行命令并返回结果
    
    Args:
        config: 配置对象
        command: 要执行的命令（字符串或列表）
        timeout: 最大运行时间（秒）
    
    Returns:
        成功返回 True，失败返回错误信息字符串
    """
    client = docker.from_env()
    container = None
    
    try:
        # 强制重建镜像和容器
        build_docker_image(client, config, force_rebuild=True)
        container = get_or_create_container(client, config, force_recreate=True)
        
        # 将命令转换为列表格式
        if isinstance(command, str):
            cmd_list = command.split()
        else:
            cmd_list = command
        
        # 在容器中执行命令
        logger.info(f"Executing command in container: {' '.join(cmd_list)}")
        result = container.exec_run(
            cmd=cmd_list,
            stdout=True,
            stderr=True,
            timeout=int(timeout)
        )
        
        # 收集输出（exec_run 将 stdout 和 stderr 合并输出）
        output = result.output.decode('utf-8', errors='replace') if result.output else ''
        exit_code = result.exit_code
        
        # 检查执行结果
        if exit_code != 0:
            error_msg = f"Command exited with code {exit_code}\n"
            error_msg += f"Output:\n{output}"
            logger.error(error_msg)
            cleanup_container(container)
            return error_msg
        
        logger.info(f"Command executed successfully:\n{output}")
        cleanup_container(container)
        return True
        
    except Exception as e:
        # 检查是否是超时异常
        error_str = str(e).lower()
        if 'timeout' in error_str or 'timed out' in error_str:
            error_msg = f"Command execution timed out after {timeout} seconds"
        else:
            error_msg = f"Error executing command: {str(e)}"
        logger.error(error_msg)
        if container:
            try:
                cleanup_container(container)
            except Exception:
                pass
        return error_msg


def connect_to_mcp_server(config: Configuration, reuse_existing: bool = False) -> docker.models.containers.Container:
    """连接到 Docker 容器中的 MCP 服务器，作为 stdio 代理"""
    client = docker.from_env()
    build_docker_image(client, config, force_rebuild=not reuse_existing)
    container = get_or_create_container(client, config, force_recreate=not reuse_existing)
    
    server_command = ['/app/.venv/bin/python', '/app/shield_mcp/proxy_mcp.py', '--mcp', '/app/mcp.json']
    
    # 使用 PIPE 捕获 stderr，同时保持 stdout/stdin 用于 MCP 通信
    stderr_lines = []
    error_detected = threading.Event()
    
    process = subprocess.Popen(
        ['docker', 'exec', '-i', container.id] + server_command,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=subprocess.PIPE,
        bufsize=0
    )
    
    def collect_stderr():
        """在后台线程中收集 stderr 输出"""
        try:
            while True:
                line = process.stderr.readline()
                if not line:
                    break
                line_str = line.decode('utf-8', errors='replace').rstrip()
                stderr_lines.append(line_str)
                
                # 检测关键错误关键词
                error_keywords = ['Traceback', 'ImportError', 'ModuleNotFoundError', 
                                'FileNotFoundError', 'RuntimeError', 'Exception', 
                                'ERROR:', 'Error:', 'Failed to']
                if any(keyword in line_str for keyword in error_keywords):
                    error_detected.set()
                    logger.error(f"Server error detected: {line_str}")
        except Exception:
            pass
    
    stderr_thread = threading.Thread(target=collect_stderr, daemon=True)
    stderr_thread.start()
    
    try:
        process.wait()
        
        # 检查进程退出码和错误
        if process.returncode != 0 or error_detected.is_set():
            error_msg = '\n'.join(stderr_lines[-50:])  # 收集最后50行错误信息
            logger.error(f"MCP server exited with code {process.returncode}")
            logger.error(f"Error output:\n{error_msg}")
            cleanup_container(container)
            raise RuntimeError(f"MCP server failed (exit code: {process.returncode}):\n{error_msg}")
            
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
        cleanup_container(container)
        raise
    
    return container


def main():
    """主函数，可以被 MCP 客户端通过 stdio 调用"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--reuse', action='store_true')
    args, _ = parser.parse_known_args()
    reuse_existing = args.reuse or os.environ.get('MCP_CONNECT_REUSE', 'false').lower() == 'true'
    
    cache_dir = os.path.join(_project_root, 'cache')
    os.makedirs(cache_dir, exist_ok=True)
    log_file_path = os.path.join(cache_dir, 'connect.log')
    
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8', mode='w')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers = [file_handler]
    
    Configuration.load_from_yaml('config.yaml')
    container = connect_to_mcp_server(Configuration, reuse_existing=reuse_existing)
    cleanup_container(container)




if __name__ == "__main__":
    main()
