# Use a slim Python image
FROM python:3.12-slim-bookworm

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy your project files
COPY . .

# Install dependencies
RUN uv sync --frozen

# Run the MCP server
ENTRYPOINT ["uv", "run", "--quiet", "flet-mcp-server"]
