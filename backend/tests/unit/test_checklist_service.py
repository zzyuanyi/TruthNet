# -*- coding: utf-8 -*-
"""核查导航服务（checklist_service）单元测试。

8/23 答辩叙事落地：L2 行动建议（规则→核查动作映射）的确定性渲染。
边界：动作不做定性/处置/预测（框架：结论可落地性分析框架 §六）。
"""

from app.application.services.checklist_service import (
    RULE_ACTIONS,
    build_rule_actions,
    pick_checklist_rules,
    render_checklist_markdown,
)


def test_all_rules_have_exactly_three_actions():
    """R1-R7 每条规则恰好 3 条常识级核查动作。"""
    for rid in ("R1", "R2", "R3", "R4", "R5", "R6", "R7"):
        assert rid in RULE_ACTIONS, f"缺少 {rid} 动作"
        assert len(RULE_ACTIONS[rid]) == 3, f"{rid} 动作数 != 3"


def test_actions_are_common_sense_without_boundary_violations():
    """措辞边界：不得出现处置/定性命词（买入/卖出/清仓/处置/存在造假）。"""
    forbidden = (
        "买入",
        "卖出",
        "清仓",
        "增持",
        "减持",
        "应予处置",
        "存在造假",
        "属于造假",
    )
    for rid, actions in RULE_ACTIONS.items():
        for action in actions:
            for word in forbidden:
                assert word not in action, f"{rid} 动作越界: {action}"


def test_unknown_rule_fail_closed():
    """未知规则 → 空动作（不硬凑）。"""
    assert build_rule_actions("R9") == []
    assert build_rule_actions("") == []


def test_pick_checklist_rules_severity_ordering():
    """排序：red > orange > yellow；同 severity 按规则 ID。"""
    picked = pick_checklist_rules(
        [("R2", "yellow"), ("R6", "red"), ("R1", "orange"), ("R4", "orange")]
    )
    assert [rid for rid, _ in picked] == ["R6", "R1", "R4"]


def test_pick_checklist_rules_limit_and_filter():
    """超过 limit 条截断；未知规则（不在映射表）剔除。"""
    picked = pick_checklist_rules(
        [("R1", "red"), ("R2", "red"), ("R3", "red"), ("R4", "red"), ("R9", "red")],
        limit=3,
    )
    assert [rid for rid, _ in picked] == ["R1", "R2", "R3"]


def test_render_empty_returns_empty_string():
    """无有效触发规则 → 空串（调用方不渲染段落）。"""
    assert render_checklist_markdown([]) == ""
    assert render_checklist_markdown([("R9", "red")]) == ""


def test_render_format():
    """渲染格式：【核查建议】标题 + 编号条目（规则 + 动作，以 · 连接）。"""
    md = render_checklist_markdown([("R1", "red"), ("R6", "orange")])
    lines = md.splitlines()
    assert lines[0] == "【核查建议】"
    assert len(lines) == 1 + 6  # 标题 + 2 规则 × 3 动作
    assert lines[1].startswith("1. R1 应收–营收背离 · ")
    assert lines[4].startswith("4. R6 其他应收款与关联占用 · ")
    assert "核母公司报表应收账款明细" in md
    # 所有条目都带规则前缀与动作分隔符
    assert all(" · " in line for line in lines[1:])


def test_render_dedup_rules():
    """同一规则多次出现（重复触发）只渲染一次（映射按规则去重）。"""
    md = render_checklist_markdown([("R1", "red"), ("R1", "orange")])
    assert md.count("R1 应收–营收背离") == 3  # 仍为 3 条动作
