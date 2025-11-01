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

DOCKERFILE_DEBUG="""
### 你的任务
根据我为你提供的tools，结合报错信息，尝试利用工具完成docker镜像与容器的构建。

### 报错信息
{error_information}
### 输出格式
{format_information}
### 执行要求
1. 你无法直接写入Dockerfile文件，必须利用我提供的INSTALL和RUN工具来插入命令，然后利用write_to_dockerfile()来写入Dockerfile。
2. 我在docker中运行的命令为{command_information}，你无需在Dockerfile中添加该命令。
3. 根据提供的报错信息，尝试检查是否为缺少某些安装包导致，你可以利用我提供的INSTALL工具来添加安装包。
4. 如果报错由其他原因导致，将'status'设置为'failed'，给出错误原因以及修改建议。
5. 你只有有限的直接debug能力，对于超过你能力之外的工作，请将'status'设置为'failed'。
6. 我为你提供了build_container()工具，可用于自主测试。

"""