"""编码与路径策略验证测试.

验证项目代码遵循:
- 所有文本读写使用 UTF-8
- 路径使用 pathlib.Path
- 不硬编码盘符、用户名、绝对路径
- 脚本入口有 Windows UTF-8 保护
"""

from pathlib import Path

import pytest


def test_this_test_file_uses_utf8():
    """验证本测试文件可以用 UTF-8 正确读取."""
    content = Path(__file__).read_text(encoding="utf-8")
    assert len(content) > 0
    assert "encoding" in content  # 本文件至少提到了 encoding


def test_pathlib_import_in_scripts():
    """验证核心脚本使用了 pathlib."""

    repo_root = Path(__file__).resolve().parent.parent.parent
    scripts_to_check = [
        repo_root / "scripts" / "doctor.py",
        repo_root / "scripts" / "check_env.py",
        repo_root / "scripts" / "encoding_path_audit.py",
        repo_root / "scripts" / "git_safety_check.py",
        repo_root / "scripts" / "env_bootstrap.py",
        repo_root / "scripts" / "start_session.py",
        repo_root / "scripts" / "end_session.py",
    ]

    for script_path in scripts_to_check:
        if not script_path.exists():
            continue
        content = script_path.read_text(encoding="utf-8")
        assert (
            "from pathlib import Path" in content or "import pathlib" in content
        ), f"{script_path.name} 未导入 pathlib"


def test_scripts_have_utf8_stdout_protection():
    """验证核心脚本有 Windows UTF-8 控制台保护."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    scripts_to_check = [
        repo_root / "scripts" / "doctor.py",
        repo_root / "scripts" / "check_env.py",
        repo_root / "scripts" / "encoding_path_audit.py",
        repo_root / "scripts" / "git_safety_check.py",
        repo_root / "scripts" / "env_bootstrap.py",
        repo_root / "scripts" / "start_session.py",
        repo_root / "scripts" / "end_session.py",
    ]

    for script_path in scripts_to_check:
        if not script_path.exists():
            continue
        content = script_path.read_text(encoding="utf-8")
        # 检查是否有 sys.stdout.reconfigure(encoding="utf-8", ...) 或类似保护
        has_protection = (
            "sys.stdout.reconfigure" in content or "sys.stderr.reconfigure" in content
        )
        assert has_protection, f"{script_path.name} 缺少 Windows UTF-8 控制台保护"


def test_main_py_uses_pathlib():
    """验证 main.py 使用了 pathlib."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    main_path = repo_root / "backend" / "app" / "main.py"
    content = main_path.read_text(encoding="utf-8")
    assert "from pathlib import Path" in content
    # .env 路径使用 pathlib
    assert "Path(__file__)" in content


def test_schemas_use_encoding_in_file_ops():
    """验证 schema 文件中如果有文件操作，使用了 encoding 参数."""

    repo_root = Path(__file__).resolve().parent.parent.parent
    schemas_dir = repo_root / "backend" / "app" / "schemas"

    for py_file in schemas_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        if "open(" in content:
            # 如果有 open() 调用，必须包含 encoding
            # 注意：这只是一个粗略检查
            lines_with_open = [
                line
                for line in content.splitlines()
                if "open(" in line
                and "encoding" not in line
                and not line.strip().startswith("#")
            ]
            # 排除二进制模式
            suspicious = [
                line
                for line in lines_with_open
                if '"rb"' not in line
                and "'rb'" not in line
                and '"wb"' not in line
                and "'wb'" not in line
            ]
            assert (
                len(suspicious) == 0
            ), f"{py_file.name} 包含裸 open() 无 encoding: {suspicious}"


def test_no_hardcoded_drive_letters_in_backend():
    """验证后端代码中无硬编码盘符."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    backend_dir = repo_root / "backend"

    drive_patterns = [
        r"[A-Za-z]:\\\\",
        r"[A-Za-z]:/",
    ]

    for py_file in backend_dir.rglob("*.py"):
        # 跳过本测试文件自身（定义了搜索模式）
        if py_file.name == "test_encoding_path_policy.py":
            continue

        content = py_file.read_text(encoding="utf-8")
        for lineno, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # 跳过模式定义行和文档示例行
            if "drive_patterns" in stripped or "禁止" in stripped:
                continue
            for pat in drive_patterns:
                if pat in line.replace("'", '"'):
                    assert False, f"{py_file}:{lineno} 包含硬编码盘符: {stripped[:80]}"


def test_editorconfig_exists():
    """验证 .editorconfig 存在并配置了 UTF-8 和 LF."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    editorconfig = repo_root / ".editorconfig"
    assert editorconfig.exists(), ".editorconfig 缺失"

    content = editorconfig.read_text(encoding="utf-8")
    assert "charset = utf-8" in content
    assert "end_of_line = lf" in content


def test_gitattributes_exists():
    """验证 .gitattributes 存在."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    gitattributes = repo_root / ".gitattributes"
    assert gitattributes.exists(), ".gitattributes 缺失"

    content = gitattributes.read_text(encoding="utf-8")
    assert "text=auto" in content or "text = auto" in content
    assert "eol=lf" in content or "eol = lf" in content


def test_gitignore_covers_sensitive_files():
    """验证 .gitignore 覆盖了敏感文件."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    gitignore = repo_root / ".gitignore"
    content = gitignore.read_text(encoding="utf-8")

    required_entries = [
        ".env",  # 环境变量
        ".venv",  # 虚拟环境
        "node_modules",  # 前端依赖
        "*.db",  # 数据库
        "*.sqlite",  # 数据库
    ]
    for entry in required_entries:
        assert entry in content, f".gitignore 缺少 {entry}"


# ── 审计文件收集回归（中文路径 / 点文件 / NUL 分割） ────────


def _load_audit_module():
    """加载审计脚本模块（避免顶层 import 副作用）。"""
    import importlib.util
    import sys

    repo_root = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "encoding_path_audit", repo_root / "scripts" / "encoding_path_audit.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _git_exe() -> str:
    """解析 git 可执行文件；不可用时跳过（测试依赖 git）。"""
    import shutil

    git_exe = shutil.which("git")
    if git_exe is None:
        pytest.skip("git 不可用，跳过 git 相关回归测试")
    return git_exe


@pytest.fixture
def git_on_path(monkeypatch):
    """把 git 所在目录加入 PATH（审计脚本 subprocess 调用依赖 PATH）。"""
    import os

    git_dir = str(Path(_git_exe()).parent)
    monkeypatch.setenv("PATH", git_dir + os.pathsep + os.environ.get("PATH", ""))


def _init_git_repo(tmp_path):
    """tmp_path 初始化为 git 仓库并提交全部文件。"""
    import subprocess

    git = _git_exe()
    subprocess.run([git, "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run([git, "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        [git, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "t"],
        cwd=tmp_path,
        check=True,
    )


def test_git_listed_files_handles_chinese_paths(tmp_path, git_on_path):
    """P2 回归：中文文件名经 git ls-files 不转义、不静默漏扫。

    core.quotepath 默认对中文输出八进制转义，Path.is_file() 失效导致漏扫。
    """
    audit = _load_audit_module()
    (tmp_path / "中文文档.md").write_text("测试", encoding="utf-8")
    (tmp_path / "普通.md").write_text("x", encoding="utf-8")
    _init_git_repo(tmp_path)

    files = audit._git_listed_files(tmp_path)
    assert files is not None, "git ls-files 应可用"
    names = [f.name for f in files]
    assert "中文文档.md" in names, "中文文件不得被转义漏扫"
    assert "普通.md" in names


def test_dotfiles_and_env_example_scanned(tmp_path, git_on_path):
    """P3 回归：.gitignore/.env.example 等点文件（suffix 为空/不匹配）应被扫描。"""
    audit = _load_audit_module()
    (tmp_path / ".gitignore").write_text("x", encoding="utf-8")
    (tmp_path / ".env.example").write_text("x", encoding="utf-8")
    (tmp_path / "普通.md").write_text("x", encoding="utf-8")
    _init_git_repo(tmp_path)

    text_files = audit.iter_text_files(tmp_path)
    names = {f.name for f in text_files}
    assert ".gitignore" in names, "点文件 suffix 为空仍应被扫描"
    assert ".env.example" in names, ".env.example 应命中 name 判断"


def test_walk_files_prunes_ignore_prefixes(tmp_path):
    """P2 回归：回退 walk 按完整路径剪枝，目录本身（data/raw）不下钻。

    曾只 startswith("data/raw/")——目录 rel_str="data/raw" 不命中，
    data/raw、.claude/skills 仍被完整遍历。
    """
    audit = _load_audit_module()
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "a.md").write_text("x", encoding="utf-8")
    deep = raw / "deep"
    deep.mkdir(parents=True, exist_ok=True)
    (deep / "b.md").write_text("x", encoding="utf-8")
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    (skills / "s.md").write_text("x", encoding="utf-8")
    (tmp_path / "keep.md").write_text("x", encoding="utf-8")

    files = audit._walk_files(tmp_path)
    paths = {str(f.relative_to(tmp_path)).replace("\\", "/") for f in files}
    assert "keep.md" in paths
    assert not any(p.startswith("data/raw") for p in paths), "data/raw 不应下钻"
    assert not any(
        p.startswith(".claude/skills") for p in paths
    ), ".claude/skills 不应下钻"
