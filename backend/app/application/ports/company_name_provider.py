"""CompanyNameIndexProvider Port — v3.3.3 收口批次 B（方案 §3.3）。

exact_company_spotter 的名称索引数据访问边界：spotter 是 application
service，不得自行创建 SQLAlchemy Engine、不得读取 settings；完整公司
名称集合由 infrastructure adapter 提供（MySQL/SQLite 同一契约）。

缓存 key（profile_key）必须区分 backend/database/profile，避免测试库
与演示库名称索引互用。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CompanyNameIndexProvider(Protocol):
    """公司完整名称索引 provider（spotter 唯一数据入口）。"""

    @property
    def profile_key(self) -> str:
        """缓存隔离 key：backend/host/database 等身份组成。"""
        ...

    def list_company_names(self) -> frozenset[str]:
        """一次性返回全部完整名称（sec_name + 有效 aliases），不做 LIMIT 截断。"""
        ...
