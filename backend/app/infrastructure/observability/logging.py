"""结构化日志 — V12 baseline.

基于 structlog（如可用）或标准 logging。
"""

import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    """配置日志.

    在 lite profile 下使用标准 logging。
    full profile 下可切换 structlog。
    """
    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(log_format))

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)

    # 尝试使用 structlog
    try:
        import structlog

        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.dev.ConsoleRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        logging.getLogger(__name__).info("structlog 已启用")
    except ImportError:
        logging.getLogger(__name__).info("structlog 未安装，使用标准 logging")
