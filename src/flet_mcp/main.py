import logging
import os
import sys

from flet_mcp.server import mcp

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

VALID_TRANSPORTS = ("stdio", "sse", "streamable-http")


def _transport_kwargs(transport: str) -> dict:
    if transport == "stdio":
        return {}
    return {
        "host": os.environ.get("FLET_MCP_HOST", "127.0.0.1"),
        "port": int(os.environ.get("FLET_MCP_PORT", "8000")),
    }


def run_server():
    """Entry point for the uv script execution.

    Transport is stdio by default; set FLET_MCP_TRANSPORT=sse|streamable-http
    (plus FLET_MCP_HOST/FLET_MCP_PORT) to serve over HTTP instead.
    """
    transport = os.environ.get("FLET_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in VALID_TRANSPORTS:
        logger.error(
            "FLET_MCP_TRANSPORT must be one of %s, got '%s'",
            ", ".join(VALID_TRANSPORTS),
            transport,
        )
        sys.exit(1)
    kwargs = _transport_kwargs(transport)
    if kwargs:
        logger.info(
            "Serving Flet MCP Server on %s at %s:%s", transport, kwargs["host"], kwargs["port"]
        )
    try:
        mcp.run(transport=transport, **kwargs)
    except Exception as e:
        logging.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_server()
