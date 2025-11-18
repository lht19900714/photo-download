import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List


def setup_logging(log_dir: Path, log_level: str = "INFO") -> Path:
    """
    初始化日志，控制台 + 轮转文件。
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "run.log"

    # 避免重复添加 handler
    if logging.getLogger().handlers:
        return log_file

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO), handlers=[console_handler, file_handler])

    return log_file


def tail_log(log_file: Path, tail: int = 200) -> List[str]:
    """
    读取日志文件尾部若干行。
    """
    if not log_file.exists():
        return []

    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    return lines[-tail:]
