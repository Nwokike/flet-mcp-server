import logging
import sys
from flet_mcp.server import mcp

# Force all logging to stderr so it doesn't interfere with MCP messages on stdout
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

def run_server():
    """
    Entry point for the uv script execution.
    """
    try:
        mcp.run(transport='stdio')
    except Exception as e:
        logging.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_server()
