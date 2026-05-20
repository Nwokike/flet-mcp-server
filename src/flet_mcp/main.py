import logging
import sys

from flet_mcp.server import mcp

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def run_server():
    """Entry point for the uv script execution."""
    try:
        mcp.run(transport="stdio")
    except Exception as e:
        logging.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_server()
