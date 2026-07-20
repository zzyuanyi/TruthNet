"""Custom reducers — V12 §7.3.

每个 reducer 满足确定性、幂等、可测试。
并行节点只能写入自己负责的命名空间。
"""

from app.agents.state import Claim, EvidenceRef, ModuleResults, ModuleStatus


def merge_module_status(
    a: dict[str, ModuleStatus], b: dict[str, ModuleStatus]
) -> dict[str, ModuleStatus]:
    """合并模块状态。b 中的键覆盖 a 中同键，实现状态更新。"""
    return {**a, **b}


def merge_module_results(a: ModuleResults, b: ModuleResults) -> ModuleResults:
    """合并模块结果。后写入的覆盖先写入的同字段。

    并行节点各自只写自己的命名空间（finance/equity/events），
    所以不会互相覆盖。
    """
    return ModuleResults(
        finance=b.finance or (a and a.finance),
        equity=b.equity or (a and a.equity),
        events=b.events or (a and a.events),
    )


def merge_evidence(a: list[EvidenceRef], b: list[EvidenceRef]) -> list[EvidenceRef]:
    """拼接证据列表。后追加的证据排后面。"""
    return a + b


def merge_claims(a: list[Claim], b: list[Claim]) -> list[Claim]:
    """拼接 Claim 列表。后追加的 Claim 排后面。"""
    return a + b
