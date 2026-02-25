import os
import logging
from logging.handlers import TimedRotatingFileHandler
from colorama import Fore, Style


LOG_DIR = os.environ.get("LOG_DIR", os.path.join(os.path.dirname(__file__), "logs"))


class ColorFormatter(logging.Formatter):
    COLORS = {logging.DEBUG: Fore.CYAN, logging.INFO: Fore.GREEN, logging.WARNING: Fore.YELLOW, logging.ERROR: Fore.RED, logging.CRITICAL: Fore.MAGENTA}
    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"
        return super().format(record)


def setup_logger(name="plantcam"):
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    file_handler = TimedRotatingFileHandler(os.path.join(LOG_DIR, "plantcam.log"), when="midnight", interval=1, backupCount=30)
    file_handler.setFormatter(logging.Formatter(fmt))
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter(fmt))
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    return logger
