"""
Logger
======
Professional logging setup with file + console output.
"""

import logging
import os
from datetime import datetime
from pathlib import Path


def setup_logger(log_file: str = "logs/bot.log", verbose: bool = True) -> logging.Logger:
    """Set up application logger."""
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("botattack")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s │ %(levelname)-8s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)

    return logger
