from typing import Any, Optional
from langchain_core.runnables import RunnableConfig
from dataclasses import dataclass, fields
import os
import yaml

@dataclass
class Configuration:
    """Configuration for the workflow/graph-based implementation (graph.py)."""
    openai_model: str = 'qwen3-max'
    openai_api_url: str = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    openai_api_key: str = "sk-c0d3d24b6eab4b9fbbf654c2a8817980"

    mcp_config_path: str = 'mcp.json'
    docker_build_path: str = 'dockers/'
    docker_image_name: str = 'shield_v2:latest'

    # 默认的CMD命令
    default_cmd: str = "/app/.venv/bin/python /app/shield_mcp/proxy_mcp.py"
    default_debug_cmd: str = "/app/.venv/bin/python /app/shield_mcp/proxy_mcp.py --debug"


    @staticmethod
    def load_from_yaml(yaml_path: str) -> None:
        """从YAML文件加载配置"""
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        for field_name, value in config_data.items():
            setattr(Configuration, field_name, value)

    @classmethod
    def from_config(cls, config: dict) -> 'Configuration':
        current_values = {f.name: getattr(cls, f.name) for f in fields(cls) if f.init}
        values: dict[str. Any] = {
            f.name: config.get(f.name, current_values.get(f.name))
            for f in fields(cls)
            if f.init
        }
        return cls(**{k: v for k, v in values.items() if v})

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
        ) -> 'Configuration':
        """Create a Configuration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if "configurable" in config else {}
        )
        
        # 获取当前类属性的值作为默认值
        current_values = {f.name: getattr(cls, f.name) for f in fields(cls) if f.init}
        
        values: dict[str, Any] = {
            f.name: os.environ.get(f.name.upper(), configurable.get(f.name, current_values.get(f.name)))
            for f in fields(cls)
            if f.init
        }
        return cls(**{k: v for k, v in values.items() if v})        