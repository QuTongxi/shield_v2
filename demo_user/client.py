from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import logging
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('MCP_Client')

server_param = StdioServerParameters(
    command='python3',
    args=['/home/godqu/workspace/study/shield_v2/connect.py'],
)

async def main():   
    try:
        async with stdio_client(server_param) as client:
            async with ClientSession(client[0], client[1]) as session:
                await session.initialize()
                tools = await session.list_tools()
                name_list = [tool.name for tool in tools.tools]
                
                logger.info(f"Successfully connected! Found {len(name_list)} tools:")
                logger.info(f"{name_list}")
                return True
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return False

async def test_tool():
    while True:
        logger.info("Starting connection test...")
        success = await main()
        if success:
            logger.info("Connection test completed successfully")
        else:
            logger.error("Connection test failed")
        
        # 等待随机时间（1-5秒）再连接
        wait_time = random.uniform(1.0, 5.0)
        logger.info(f"Waiting {wait_time:.2f} seconds before next connection...")
        await asyncio.sleep(wait_time)

asyncio.run(test_tool())