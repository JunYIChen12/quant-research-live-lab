# ADR-20260918 项目治理流程简化

## 背景

PR #14 的产品代码、定向/全量测试、Ruff、CI 和 fail-closed 场景均通过，首次独立验收仍因人工 SHA-256 表的转录错误和未标明快照的历史测试数量漂移进入 REWORK。重复人工证据没有增加安全性，反而阻断了可复核交付。

## 决定

继续以 GitHub Issue/PR、CI、精确 Pull Request HEAD、diff/敏感信息检查和独立验收作为正式证据。治理脚本按 PR 文件路径做确定分类：L0 仅为现有小文档例外；L1 仅为明确的普通研究/数据处理代码及其普通测试；发布、验证、Dry-run、风控、配置、权限、安全、Actions、治理和任何未知或混合路径均按高风险处理。

L1 可从已确认 Issue/PR 直接进入 `IN_PROGRESS`，再经过 `READY_FOR_VERIFY -> ACCEPTED -> CLOSED`；高风险仍必须经过完整的 `DRAFT -> ANALYZING -> READY -> IN_PROGRESS` 链。两条路径都保留精确 HEAD 验收、后续提交失效、REWORK/BLOCKED 和合并关闭门禁。

## 未采用

- 不新增数据库、审批服务、依赖或通用规则引擎。
- 不用手工 SHA 表、历史测试总数或 Playwright/视觉检查作为非 UI 任务的硬门禁。
- 不改变真实 Dry-run、交易所、凭据、实盘、风险限额、release、validation 或 dry_run 产品逻辑。

## 影响与回滚

未知路径默认高风险，宁可要求完整审查也不放宽门禁。回滚通过受治理的反向 Pull Request 完成，不直接改写 `main` 或 `status:*` 标签。

## 验证

治理测试覆盖 L0、L1 紧凑路径、未知路径高风险、完整状态链、精确 HEAD、验收失效和合并关闭；全量测试与 CI 继续作为合并前检查。
