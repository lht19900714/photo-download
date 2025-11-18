import logging
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Deque, List, Tuple


class _MemoryLogHandler(logging.Handler):
    def __init__(self, capacity: int = 1000):
        super().__init__()
        self.buffer: Deque[Tuple[int, str]] = deque(maxlen=capacity)
        self._counter = 0

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self._counter += 1
        self.buffer.append((self._counter, msg + "\n"))

    def tail(self, count: int) -> List[str]:
        if count <= 0:
            return []
        return [line for _, line in list(self.buffer)[-count:]]

    def since(self, last_seq: int) -> Tuple[List[str], int]:
        lines: List[str] = []
        new_seq = last_seq
        for seq, line in self.buffer:
            if seq > last_seq:
                lines.append(line)
                new_seq = seq
        return lines, new_seq


_memory_handler: _MemoryLogHandler | None = None


def setup_logging(log_dir: Path, log_level: str = "INFO") -> Path:
    """
    初始化日志，控制台 + 轮转文件。
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "run.log"

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

    global _memory_handler
    if _memory_handler is None:
        _memory_handler = _MemoryLogHandler(capacity=2000)
        _memory_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 避免重复添加相同类型的 handler
    handler_types = {type(h) for h in root.handlers}
    if RotatingFileHandler not in handler_types:
        root.addHandler(file_handler)
    if logging.StreamHandler not in handler_types:
        root.addHandler(console_handler)
    if _MemoryLogHandler not in handler_types:
        root.addHandler(_memory_handler)

    return log_file


def tail_log(log_file: Path, tail: int = 200) -> List[str]:
    """
    读取日志文件尾部若干行。
    """
    if not log_file.exists():
        return get_buffer_lines(tail)

    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    return lines[-tail:]


def get_buffer_lines(tail: int = 200) -> List[str]:
    if _memory_handler is None:
        return []
    return _memory_handler.tail(tail)


def get_buffer_since(last_seq: int) -> Tuple[List[str], int]:
    if _memory_handler is None:
        return [], last_seq
    return _memory_handler.since(last_seq)
