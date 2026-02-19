from config import Config
import logging
import sys

logger = logging.getLogger("workers")
logger.setLevel(getattr(logging, Config.LOG_LEVEL))

if not logger.hasHandlers():
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
