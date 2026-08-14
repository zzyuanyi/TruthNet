"""已废弃：行业分类 akshare 补全（历史任务⑤脚本）。

2026-08-14 起废弃（《行业分类覆盖补全-具体修复档案》v1.1 §3.2 处置方案 2）：

- 正式入口唯一：`scripts/industry_fill.py`；
- 本文件不再执行任何数据库写入与网络请求；
- 原硬编码 L2_TO_L1 映射表已迁移至
  `backend/app/application/services/industry_fill/normalizer.py`（带映射版本与
  申万一级允许集合校验）；
- 原依赖的 `data/raw/比赛数据` 路径已失效，不再使用。

如需行业补全，请运行：

    python scripts/industry_fill.py --database <truthnet_test|truthnet> --help

（文件保留仅为历史溯源与迁移提示，待团队流程决定是否删除。）
"""

from __future__ import annotations

import sys


def main() -> int:
    print(__doc__)
    return 2  # 非零退出：提示调用方入口已迁移


if __name__ == "__main__":
    sys.exit(main())
