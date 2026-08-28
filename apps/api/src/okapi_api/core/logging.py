"""Structured logging setup (architecture doc section 8)."""

import logging
import sys

_FORMAT = '{"ts":"%(asctime)s","level":"%(levelname)s",' '"logger":"%(name)s","msg":"%(message)s"}'


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
