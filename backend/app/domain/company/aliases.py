"""aliases JSON 规范化共享函数（2026-08-12 四轮审查 P2-1 抽取）。

resolve_entity 对话解析与 MySQLCompanyRepository 共用同一实现，
避免 dict/嵌套 list 形态下"画像搜索能识别而 WS 不能"。
"""

import json

# 哨兵：最外层 str 被判定为非法 JSON（而非普通别名文本）
_INVALID_JSON = object()


def json_decode_once(raw):
    """仅对**最外层** str 尝试 JSON 解码（数据库列原始值）。

    非法 JSON → _INVALID_JSON 哨兵（展开时视为空）。
    嵌套结构里的字符串元素是已解析值，不再二次解码。
    """
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return _INVALID_JSON
    return raw


def expand_aliases(value) -> list[str]:
    """递归展开任意 dict / 嵌套 list / 字符串值；去空白。"""
    if value is None or value is _INVALID_JSON:
        return []
    if isinstance(value, dict):
        out: list[str] = []
        for v in value.values():
            out.extend(expand_aliases(v))
        return out
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(expand_aliases(item))
        return [s for s in out if s]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return []


def aliases_to_list(raw) -> list[str]:
    """将 aliases 规范为字符串列表（JSON 解码与递归展开分离）。

    覆盖任意 dict / 嵌套 list / 字符串值 / 非法 JSON。
    """
    return expand_aliases(json_decode_once(raw))
