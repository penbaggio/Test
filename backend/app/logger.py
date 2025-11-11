"""日志配置模块"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 创建日志目录
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 日志级别
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 日志格式
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 创建格式化器
formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)


def get_logger(name: str) -> logging.Logger:
    """
    获取配置好的日志记录器
    
    Args:
        name: 日志记录器名称
    
    Returns:
        配置好的Logger对象
    """
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    # 文件Handler - 应用日志
    app_handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(formatter)
    logger.addHandler(app_handler)
    
    # 文件Handler - 错误日志
    error_handler = RotatingFileHandler(
        LOG_DIR / "error.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    # 控制台Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if os.getenv("DEBUG") else logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


# 创建默认logger
logger = get_logger("trading_system")
