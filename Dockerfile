FROM python:3.11-slim-bookworm

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy your project files
COPY . .

# Ensure Python output is unbuffered to prevent logging delays
ENV PYTHONUNBUFFERED=1

# Install dependencies silently
RUN uv sync --frozen --no-cache

# Run the server quietly
ENTRYPOINT ["uv", "run", "--quiet", "flet-mcp-server"]
