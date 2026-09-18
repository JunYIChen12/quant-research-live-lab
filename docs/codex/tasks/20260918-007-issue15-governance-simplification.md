# 20260918-007 Issue #15 项目流程简化实施证据

## 基线与范围

- 工作树：`C:/Users/18501/.codex/worktrees/333a/quant-research-live-lab`
- 分支：`codex/15-simplify-governance-flow`
- 基线：`main@ba1c7c0418c2f00b8b3fc89c0d81cbfd8a036ad3`
- 只修改治理脚本、治理测试、项目治理/工作流文档、稳定状态入口、CHANGELOG 和 ADR；不修改交易、风控、凭据、实盘或发布产品逻辑。

## 实施结果

- 变更分类由 PR 文件路径确定：L0 小文档、明确 L1 普通研究/测试路径；发布、验证、Dry-run、风控、配置、Actions、治理、安全和未知路径按 HIGH 处理。
- L1 Draft PR 可在 Issue 仍为 `DRAFT`、`ANALYZING` 或 `READY` 时通过治理检查，并可在有责任人、分支和开放 PR 时直接进入 `IN_PROGRESS`。
- HIGH 变更仍拒绝跳过完整状态链；精确 HEAD、独立验收、后续提交失效、REWORK 和合并关闭逻辑保留。
- `docs/codex` 不再逐阶段镜像 GitHub；已将 Issue #13/PR #14 合并关闭和 `main` 基线写入稳定事实。

## 红绿证据

- 旧实现：新增测试在收集阶段失败，`ImportError: cannot import name 'classify_change_files'`。
- 新实现：治理定向测试通过。

## 未执行与限制

- 未启动 Dry-run、未连接交易所、未读取真实凭据或账户数据。
- 非 UI 任务不执行 Playwright 或视觉检查；历史测试数量不作为硬门禁。
- 独立验收、`/verify`、ACCEPTED、合并和关闭由后续责任线程执行，本线程不代行。
