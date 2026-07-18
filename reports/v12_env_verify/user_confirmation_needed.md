# 需要用户确认事项

## 环境

1. **当前 shell 是 base (Python 3.12.7)**: 所有验证已通过直接调用 truthnet Python 完成。建议在终端执行 `conda activate truthnet` 切换到项目环境。

2. **pre-commit 未运行**: 运行 `pre-commit install` 安装 hooks 后再用 `pre-commit run --all-files` 验证。

## 代码

3. **新增文件未提交**: 本轮新增/修改的文件（requirements.txt, .env.example, scripts/verify_v12_stack.py, reports/v12_env_verify/*）尚未提交。按项目规范，不应自动 commit，请人工审阅后提交。

4. **Alembic 未初始化**: `alembic init` 尚未运行，迁移目录 `backend/app/infrastructure/persistence/migrations/` 为空骨架。

## 预存问题（非本轮引入）

5. **encoding_path_audit 12 FAIL**: 全部为测试用例和文档示例中故意使用的硬编码路径（用于教学目的），不影响实际代码。

6. **git_safety_check 1 FAIL**: 当前在 main 分支 — 这是任务约定状态，开发时请切换到 feature 分支。

7. **test_stack_smoke sklearn fail**: numpy 2.x 与 scipy 编译版本不兼容 — 预存问题。
