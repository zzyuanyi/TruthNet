"""编码与路径策略验证测试.

验证项目代码遵循:
- 所有文本读写使用 UTF-8
- 路径使用 pathlib.Path
- 不硬编码盘符、用户名、绝对路径
- 脚本入口有 Windows UTF-8 保护
"""

from pathlib import Path


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
