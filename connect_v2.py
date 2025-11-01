import sys
import subprocess
import atexit
from deploy.docker_helper import build_all, clean_all
from utils.configuration import Configuration
import docker

Configuration.load_from_yaml('config.yaml')

client = docker.from_env()
container, info = build_all(
    client, 
    image_name = Configuration.docker_image_name,
    dockerfile = 'Dockerfile',
    build_path = Configuration.docker_build_path,
    force_rebuild = True,
)

# 注册退出时的清理函数，确保容器一定会被删除
atexit.register(clean_all)

try:
    # 使用 subprocess 直接连接 stdin/stdout
    subprocess.run(
        ['docker', 'exec', '-i', container.id, 'sh', '-c', Configuration.default_cmd],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
finally:
    # 无论如何退出（正常/异常/中断），都清理容器
    clean_all()

