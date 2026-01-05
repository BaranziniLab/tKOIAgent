"""
Logging utility for tKOIAgent MCP server.

CRITICAL: All logging MUST go to stderr to maintain STDIO transport compliance.
stdout is reserved exclusively for JSON-RPC messages.
"""

import logging
import sys
from typing import Optional


def setup_logging(level: int = logging.INFO):
    """
    Setup logging configuration for MCP server.

    IMPORTANT: All logs go to stderr to avoid polluting stdout with non-JSON-RPC content.

    Args:
        level: Logging level (default: INFO)
    """
    # Create formatter with timestamp and module information
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Create stderr handler (CRITICAL for MCP STDIO transport)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers to avoid duplication
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger('neo4j').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance configured to output to stderr
    """
    return logging.getLogger(name)
