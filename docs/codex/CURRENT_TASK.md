# 当前任务

当前任务：`20260918-006` 1.0 已验收成果持久化与远程对齐。

- 状态：`READY_FOR_VERIFY`。
- 当前责任线程：新的 `30｜验收｜20260918-006` 独立复验线程。
- 任务文件：[1.0 已验收成果持久化与远程对齐](tasks/20260918-006-accepted-baseline-integration.md)。
- GitHub 正式任务：[Issue #13](https://github.com/JunYIChen12/quant-research-live-lab/issues/13)。
- READY 契约已固定：从最新 `main` 建立隔离工作树，以一个关联 Issue #13 的 Draft PR 按白名单迁移最终文件；原始脏工作区保持只读。
- 实施基线：远程 `main` 与目标分支均为 `d524b1218746133410c409134749fe7058ddf3b2`；当前隔离工作树分支为 `codex/13-accepted-baseline-integration`。
- 原始 `D:/CodexProjects/projects/quant-research-live-lab` 工作区只读；仅允许迁移任务文件中列出的产品、测试、fixtures、`docs/codex` 文档及三处语义合并文件。
- Draft PR：#14；文档证据返工已交回独立验收，不关闭旧 Issue/PR，不启动 Dry-run。
- 本次返工只解决重复人工证据漂移：迁移完整性改用可重跑源/目标内容比较，稳定项目状态不维护易过期测试数量；交易、风控和发布权限不变。
- `20260916-004` 继续保持 `DRAFT`，不自动启动。
