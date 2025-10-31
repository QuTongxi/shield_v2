from deploy.create_docker import test_function, test_docker_container
from utils.configuration import Configuration
from rich.logging import RichHandler
import logging
import asyncio
import threading
import sys

logging.basicConfig(
    level=logging.WARN,
    format='%(message)s',
    handlers=[RichHandler()]
)
logging.getLogger("shield_v2").setLevel(logging.DEBUG)
logger = logging.getLogger("shield_v2.test")


async def test_scenario_1_immediate_return():
    """
    场景1：立即返回，容器和日志流在后台运行
    测试日志实时打印功能
    """
    logger.info("=" * 60)
    logger.info("场景1：立即返回，后台运行模式")
    logger.info("=" * 60)
    
    try:
        container = await test_function(Configuration)
        logger.info(f"容器已启动: {container.id[:12]}")
        logger.info("容器在后台运行，日志会实时打印到控制台")
        logger.info("按 Ctrl+C 停止...")
        
        # 让容器运行一段时间以便观察日志
        try:
            await asyncio.sleep(30)  # 运行30秒
        except KeyboardInterrupt:
            logger.info("\n接收到停止信号")
        finally:
            # 清理容器
            try:
                container.stop()
                container.remove()
                logger.info(f"容器 {container.id[:12]} 已停止并删除")
            except Exception as e:
                logger.error(f"清理容器时出错: {e}")
                
    except Exception as e:
        logger.error(f"测试场景1失败: {e}")
        raise


async def test_scenario_2_with_stop_event():
    """
    场景2：使用stop_event控制日志流停止
    测试可以主动停止日志流
    """
    logger.info("=" * 60)
    logger.info("场景2：使用stop_event控制")
    logger.info("=" * 60)
    
    stop_event = threading.Event()
    container = None
    
    try:
        # 在后台任务中启动容器
        async def run_container():
            nonlocal container
            container = await test_function(Configuration, stop_event)
            logger.info(f"容器已启动: {container.id[:12]}")
        
        container_task = asyncio.create_task(run_container())
        
        # 等待容器启动
        await asyncio.sleep(2)
        
        logger.info("容器正在运行，日志会实时打印...")
        logger.info("5秒后将停止日志流（容器继续运行）...")
        await asyncio.sleep(5)
        
        # 停止日志流
        logger.info("停止日志流...")
        stop_event.set()
        
        # 等待任务完成
        await container_task
        
        logger.info("日志流已停止，容器仍在运行")
        logger.info("等待3秒后清理容器...")
        await asyncio.sleep(3)
        
        # 清理容器
        try:
            container.stop()
            container.remove()
            logger.info(f"容器 {container.id[:12]} 已停止并删除")
        except Exception as e:
            logger.error(f"清理容器时出错: {e}")
            
    except Exception as e:
        logger.error(f"测试场景2失败: {e}")
        if container:
            try:
                container.stop()
                container.remove()
            except:
                pass
        raise


async def test_scenario_3_multiple_containers():
    """
    场景3：测试多个容器同时运行
    验证日志不会混乱
    """
    logger.info("=" * 60)
    logger.info("场景3：多个容器同时运行")
    logger.info("=" * 60)
    
    containers = []
    
    try:
        # 创建两个容器
        logger.info("启动容器1...")
        container1 = await test_docker_container(Configuration)
        containers.append(container1)
        logger.info(f"容器1已启动: {container1.id[:12]}")
        
        await asyncio.sleep(1)
        
        logger.info("启动容器2...")
        container2 = await test_docker_container(Configuration)
        containers.append(container2)
        logger.info(f"容器2已启动: {container2.id[:12]}")
        
        logger.info("两个容器都在运行，观察日志输出...")
        logger.info("10秒后清理所有容器...")
        await asyncio.sleep(10)
        
        # 清理所有容器
        for i, container in enumerate(containers, 1):
            try:
                container.stop()
                container.remove()
                logger.info(f"容器{i} ({container.id[:12]}) 已停止并删除")
            except Exception as e:
                logger.error(f"清理容器{i}时出错: {e}")
                
    except Exception as e:
        logger.error(f"测试场景3失败: {e}")
        for container in containers:
            try:
                container.stop()
                container.remove()
            except:
                pass
        raise


async def test_scenario_4_short_run():
    """
    场景4：短时间运行测试
    快速验证功能是否正常
    """
    logger.info("=" * 60)
    logger.info("场景4：短时间运行测试")
    logger.info("=" * 60)
    
    try:
        container = await test_function(Configuration)
        logger.info(f"容器已启动: {container.id[:12]}")
        logger.info("运行5秒后自动清理...")
        await asyncio.sleep(5)
        
        # 清理容器
        try:
            container.stop()
            container.remove()
            logger.info(f"容器 {container.id[:12]} 已停止并删除")
        except Exception as e:
            logger.error(f"清理容器时出错: {e}")
            
    except Exception as e:
        logger.error(f"测试场景4失败: {e}")
        raise


async def main():
    """主测试函数"""
    logger.info("开始测试 Docker 容器实时日志流功能")
    logger.info("")
    
    # 加载配置
    Configuration.load_from_yaml('config.yaml')
    
    # 获取命令行参数
    if len(sys.argv) > 1:
        scenario = sys.argv[1]
    else:
        scenario = "4"  # 默认运行场景4（快速测试）
    
    scenario_map = {
        "1": ("场景1：立即返回，后台运行", test_scenario_1_immediate_return),
        "2": ("场景2：使用stop_event控制", test_scenario_2_with_stop_event),
        "3": ("场景3：多个容器同时运行", test_scenario_3_multiple_containers),
        "4": ("场景4：短时间运行测试", test_scenario_4_short_run),
    }
    
    if scenario not in scenario_map:
        logger.error(f"未知的场景: {scenario}")
        logger.info("可用的场景:")
        for key, (name, _) in scenario_map.items():
            logger.info(f"  {key}: {name}")
        return
    
    scenario_name, scenario_func = scenario_map[scenario]
    logger.info(f"运行: {scenario_name}")
    logger.info("")
    
    try:
        await scenario_func()
        logger.info("")
        logger.info("=" * 60)
        logger.info("测试完成！")
        logger.info("=" * 60)
    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n程序被用户中断")
        sys.exit(0)