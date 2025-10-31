import os
import docker
import time
import asyncio
import queue
import threading
from utils.configuration import Configuration

import logging
logger = logging.getLogger('shield_v2.deploy.create_docker')

client = docker.from_env()
workdir = os.path.join(os.path.dirname(__file__), '..')

def build_docker_image(config:Configuration):
    try:
        logger.info(f"Building docker image from {os.path.abspath(config.docker_build_path)}")
        image, logs = client.images.build(
            path=config.docker_build_path,
            tag=config.docker_image_name.split(':')[0],
            dockerfile=os.path.join(os.path.abspath(config.docker_build_path), 'Dockerfile'),
            rm=True,
        )
        # collect logs to string
        log_text = ''
        try:
            for chunk in logs:
                logger.info(f"type of chunk: {type(chunk)}")
                if isinstance(chunk, (bytes, bytearray)):
                    log_text += chunk.decode('utf-8', errors='ignore')
                elif isinstance(chunk, dict):
                    log_text += chunk.get('stream') or chunk.get('status') or ''
                else:
                    log_text += str(chunk)
        except Exception:
            pass
        return True, log_text
    except Exception as e:
        logger.error(f"Error building docker image: {e}")
        return False, e

async def test_docker_container(config:Configuration, stop_event: threading.Event = None):
    """
    异步启动 Docker 容器（服务器模式），实时流式输出日志
    
    容器内的程序是服务器，会持续运行。日志通过独立线程实时读取并打印，
    不会累积存储。
    
    - 如果提供了 stop_event，函数会等待直到 stop_event 被设置
    - 如果没有提供 stop_event，函数会立即返回，日志流在后台持续运行
    
    Args:
        config: 配置对象
        stop_event: 可选的线程事件，用于控制何时停止日志流
    
    Returns:
        container: Docker 容器对象，可用于后续操作（停止、删除等）
    """
    container = None
    log_queue = queue.Queue()
    log_reader_thread = None
    log_printer_thread = None
    
    try:
        container = client.containers.run(
            image=config.docker_image_name,
            stdin_open=True,
            tty=False,
            detach=True,
            remove=False,
        )
        logger.info(f"Container {container.id[:12]} started, streaming logs in real-time...")
        
        # 如果没有提供 stop_event，创建一个内部事件（但不会等待它）
        if stop_event is None:
            stop_event = threading.Event()
            # 不等待，让容器和日志流在后台运行
            wait_for_stop = False
        else:
            # 如果提供了 stop_event，等待它被设置
            wait_for_stop = True
        
        def read_logs_from_container():
            """在单独线程中读取容器日志并放入队列"""
            try:
                for log_chunk in container.logs(stream=True, follow=True):
                    if stop_event.is_set():
                        break
                    try:
                        # 将日志块放入队列（线程安全的操作）
                        log_queue.put(log_chunk, timeout=1.0)
                    except queue.Full:
                        # 队列满了，跳过这条日志（这种情况很少见）
                        logger.warning("Log queue is full, skipping log chunk")
                    except Exception as e:
                        logger.debug(f"Error putting log to queue: {e}")
                        break
            except Exception as e:
                if not stop_event.is_set():
                    logger.error(f"Error reading logs from container: {e}")
                    # 如果容器异常停止，停止事件也会被设置
                    stop_event.set()
        
        def print_logs_from_queue():
            """在单独线程中从队列读取日志并实时打印"""
            try:
                while not stop_event.is_set():
                    try:
                        # 从队列获取日志块（非阻塞，带超时）
                        log_chunk = log_queue.get(timeout=0.5)
                        if log_chunk:
                            log_line = log_chunk.decode('utf-8', errors='ignore').rstrip()
                            if log_line:
                                # 直接打印日志，不累积
                                print(log_line)
                                log_queue.task_done()
                    except queue.Empty:
                        # 队列为空，继续等待
                        continue
                    except Exception as e:
                        logger.debug(f"Error processing log from queue: {e}")
            except Exception as e:
                logger.debug(f"Log printer thread ended: {e}")
        
        # 启动日志读取线程（从容器读取）
        log_reader_thread = threading.Thread(
            target=read_logs_from_container,
            daemon=True,
            name=f"LogReader-{container.id[:12]}"
        )
        log_reader_thread.start()
        
        # 启动日志打印线程（从队列读取并打印）
        log_printer_thread = threading.Thread(
            target=print_logs_from_queue,
            daemon=True,
            name=f"LogPrinter-{container.id[:12]}"
        )
        log_printer_thread.start()
        
        # 如果提供了 stop_event，等待它被设置
        if wait_for_stop:
            # 在异步函数中等待线程事件
            while not stop_event.is_set():
                await asyncio.sleep(0.1)  # 每100ms检查一次
            
            logger.info(f"Container {container.id[:12]} log streaming stopped")
            
            # 等待线程结束
            if log_reader_thread.is_alive():
                log_reader_thread.join(timeout=2.0)
            if log_printer_thread.is_alive():
                log_printer_thread.join(timeout=2.0)
        else:
            logger.info(f"Container {container.id[:12]} running in background, log streaming active")
        
        return container
        
    except Exception as e:
        logger.error(f"Error testing docker container: {e}")
        if stop_event:
            stop_event.set()
        raise
        
    # 注意：不在这里清理容器，因为这是服务器模式，容器应该持续运行
    # 调用者负责管理容器的生命周期

async def test_function(config:Configuration, stop_event: threading.Event = None):
    """
    异步测试函数，构建并启动 Docker 容器（服务器模式）
    
    Args:
        config: 配置对象
        stop_event: 可选的线程事件，用于控制何时停止容器日志流
    
    Returns:
        container: Docker 容器对象
    """
    success, logs = build_docker_image(config)
    if not success:
        raise Exception(f"Failed to build docker image: {logs}")
        
    container = await test_docker_container(config, stop_event)
    return container



