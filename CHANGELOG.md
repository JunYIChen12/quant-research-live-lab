# Changelog

## Unreleased

### 2026-09-17 GitHub 任务状态门禁

- 将 GitHub Issue 定义为正式任务状态源，`docs/codex` 保留执行证据和线程交接。
- 新增最小状态流转检查、PR 关联门禁、Issue Form 和 `governance` Actions 工作流。
- 解决本地任务状态、项目状态和 GitHub 正式交付状态可能漂移的重复问题；不改变交易、风险或发布授权。

### 2026-09-14 远程 Git 仓库治理

- 停用 Dependabot 每周生成依赖更新 PR；当前项目以个人推进为主，持续产生的未审阅依赖 PR 已构成协作噪音。
- 依赖升级改为按需要主动处理；CI 工作流和项目运行安全规则不变。
