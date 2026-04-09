"""
日志管理模块
提供统一的日志记录功能，同时支持文件日志和 GUI 回显。
"""
import logging
import os
from datetime import datetime


def setup_logger(name: str = "CanLogAnalyzer", log_dir: str = "logs") -> logging.Logger:
    """
    初始化并返回一个 Logger 实例。
    日志同时输出到控制台和文件。
    """
    _logger = logging.getLogger(name)
    if _logger.handlers:
        return _logger

    _logger.setLevel(logging.DEBUG)

    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(
        log_dir, f"can_analyzer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    # 文件 Handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)

    # 控制台 Handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    _logger.addHandler(fh)
    _logger.addHandler(ch)

    return _logger


logger = setup_logger()
