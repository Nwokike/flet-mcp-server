import logging
import sys
from flet_mcp.server import mcp

# Force all logging to stderr so it doesn't interfere with MCP messages on stdout
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

def run_server():
    """
    Entry point for the uv script execution.
    Runs the MCP server over standard input/output (stdio), 
    which is the communication protocol required by desktop AI agents.
    """
    mcp.run(transport='stdio')

if __name__ == "__main__":
    run_server()
