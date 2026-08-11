"""性能 smoke P95 分位算法单测 — 8.11 C8.

nearest-rank（ceil(q*n)-1）与空样本 N/A 语义的回归验证。
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(1, str(_REPO_ROOT / "scripts"))

from verify_phase_d_perf_smoke import _fmt_ms, _percentile, _reached  # noqa: E402


def test_percentile_empty_returns_none():
    """空样本返回 None（标 N/A），不得按 0ms 假达标。"""
    assert _percentile([], 0.95) is None


def test_percentile_single_sample():
    """单样本 P50/P95 均为该值。"""
    assert _percentile([123.456], 0.5) == 123.456
    assert _percentile([123.456], 0.95) == 123.456


def test_percentile_n5_p95_is_max():
    """n=5 时 P95 = 最大值（nearest-rank ceil(0.95*5)-1 = 4）。"""
    vals = [10.0, 20.0, 30.0, 40.0, 99.0]
    assert _percentile(vals, 0.95) == 99.0
    assert _percentile(vals, 0.5) == 30.0


def test_reached_na_not_reached():
    """N/A（无样本）不得判达成。"""
    assert _reached(None, 500) is False
    assert _reached(300.0, 500) is True
    assert _reached(600.0, 500) is False


def test_fmt_ms_na():
    """Markdown 展示 N/A；数值按 ms 显示。"""
    assert _fmt_ms(None) == "N/A"
    assert _fmt_ms(12.5) == "12.5ms"
