from typing import List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langchain_core.output_parsers import JsonOutputParser
from utils.configuration import Configuration
from pydantic import BaseModel

from agent_core import tools

import logging
logger = logging.getLogger('shield_v2.agent_core.llm')

async def run_llm_loop(
        config: RunnableConfig,
        prompt_template: str,
        output_pydantic: BaseModel,
        format_args: str,
        tool_list: List[BaseTool] = [],
        max_iterations: Optional[int] = 10
    ):
    """
    key status must in the output_pydantic, and the value of status must be completed, failed, continue.
    """
    configuration = Configuration.from_runnable_config(config)

    llm = ChatOpenAI(
        model=configuration.openai_model,
        api_key=configuration.openai_api_key,
        base_url=configuration.openai_api_url,
    )

    tool_dict = {tool.name: tool for tool in tool_list}
    if tool_list:
        llm = llm.bind_tools(tool_list)


    parser = JsonOutputParser(pydantic_object=output_pydantic)

    if 'format_information' not in format_args:
        format_args['format_information'] = JsonOutputParser(pydantic_object=output_pydantic).get_format_instructions()

    messages = [HumanMessage(content=prompt_template.format(**format_args))]
    iteration = 0
    response = None

    while iteration < max_iterations:
        iteration += 1
        logger.debug(f'iter: {iteration}')
        
        response = await llm.ainvoke(messages, config=config) 
        
        while hasattr(response, 'tool_calls') and response.tool_calls:                            
            # 执行所有工具调用
            messages.append(response)
            for tool_call in response.tool_calls:
                tool_message = tool_dict[tool_call['name']].invoke(tool_call)
                messages.append(tool_message)
            
            response = await llm.ainvoke(messages, config=config)   

        response = parser.parse(response.content)
        status = response.get('status', '---')
        if status == '---':
            logger.error(f'status is not in the response: {response}')
            raise

        if status == 'completed' or status == 'failed':
            return response
        elif status == 'continue':
            continue
        else:
            logger.error(f'unknown status: {status}')
            raise

    logger.warning(f'max iterations reached')
    return response

