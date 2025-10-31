PARSE_SERVER_INFO="""
### 你的任务
根据我提供的model content protocol配置文件的服务器内容，解析出其中包含的文件或文件夹路径并调用工具来存储它们。

### 配置文件内容
{mcp_config_content}

### 输出格式
{format_information}

### 例子
输入：
    "git": {{
    "command": "uvx",
    "args": ["mcp-server-git", "--repository", "/home/godqu/workspace/study/test_git_repo"]
    }}
调用工具：
    save_path_info(server_name="git", path="/home/godqu/workspace/study/test_git_repo")

"""

MAPPING="""
### 你的任务
实现下列路径到docker container内部路径的映射。通过调用工具实现路径映射的存储。

### 路径信息
{path_information}

### 输出格式
{format_information}

### 例子
输入：
    /home/godqu/workspace/study/test_git_repo
调用工具：
    add_mapping(host_path="/home/godqu/workspace/study/test_git_repo", docker_path="/app/test_git_repo")

"""


CONFIG_REWRITE="""
### 你的任务
根据我提供的配置文件内容以及我提供的路径映射规则，重写配置文件内容。将其中的路径信息进行替换。

### 配置文件内容
{mcp_config_content}

### 路径映射规则
{path_mappings}

### 输出格式
{format_information}

"""