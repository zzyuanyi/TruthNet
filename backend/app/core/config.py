"""配置兼容入口。

运行配置的唯一实现位于后端根目录 ``config.py``，便于部署时集中查看。
保留本模块仅为兼容既有 ``app.core.config`` 导入路径，避免业务模块重构。
"""

from config import Settings, settings

__all__ = ["Settings", "settings"]
