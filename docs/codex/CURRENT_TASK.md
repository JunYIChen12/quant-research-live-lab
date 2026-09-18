# 当前任务

当前任务：`20260918-006` 1.0 已验收成果持久化与远程对齐。

- 状态：`IN_PROGRESS`。
- 当前责任线程：`20｜实施｜20260918-006`。
- 任务文件：[1.0 已验收成果持久化与远程对齐](tasks/20260918-006-accepted-baseline-integration.md)。
- GitHub 正式任务：[Issue #13](https://github.com/JunYIChen12/quant-research-live-lab/issues/13)。
- READY 契约已固定：从最新 `main` 建立隔离工作树，以一个关联 Issue #13 的 Draft PR 按白名单迁移最终文件；原始脏工作区保持只读。
- 实施基线：远程 `main` 与目标分支均为 `d524b1218746133410c409134749fe7058ddf3b2`；当前隔离工作树分支为 `codex/13-accepted-baseline-integration`。
- 原始 `D:/CodexProjects/projects/quant-research-live-lab` 工作区只读；仅允许迁移任务文件中列出的产品、测试、fixtures、`docs/codex` 文档及三处语义合并文件。
- 当前不创建验收线程，不关闭旧 Issue/PR，不启动 Dry-run；完成验证、提交推送和 Draft PR 后进入 `READY_FOR_VERIFY`。
- `20260916-004` 继续保持 `DRAFT`，不自动启动。
