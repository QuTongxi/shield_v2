DOCKERFILE_TEMPLATE="""FROM python:3.13-slim
RUN apt-get update && apt-get install -y \\
    curl \\
    gnupg \\
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \\
    && apt-get install -y nodejs \\
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

{install_commands}

ENV PATH="/root/.local/bin:$PATH"

{env_commands}

WORKDIR /app

{other_run_commands}

{copy_commands}

COPY mcp.json ./
COPY pyproject.toml uv.lock ./
COPY shield_mcp /app/shield_mcp

RUN uv sync
CMD ["/app/.venv/bin/python", "/app/shield_mcp/proxy_mcp.py"]
"""