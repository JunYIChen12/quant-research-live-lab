# 项目状态

## 已核对基线

- 核对日期：2026-09-13；唯一目录 D:/CodexProjects/projects/quant-research-live-lab。
- 原产品基线：a5fdc77ccb54f5d4d3d704bf4a78cb0166942c28；2026-09-17 远程治理闭环复核时 `main` 为 PR #12 的 merge commit `d524b1218746133410c409134749fe7058ddf3b2`；初始化任务分支为 `codex/workbench-init`。动态状态每次以 Git 与 [当前任务](CURRENT_TASK.md) 重新核对。
- origin：https://github.com/JunYIChen12/quant-research-live-lab.git；2026-09-13 使用 git ls-remote 核对，默认分支及 main 仍为上述产品基线，写入前远程无 codex/workbench-init 分支。此次只获准推送该工作分支，不直接更新 main。
- 本次本地工具环境：Windows、PowerShell 7.6.5；没有安装或重建环境。
- 仓库存在 src/quant_lab/gates.py、release.py 及对应 tests/test_gates.py、test_release.py；这是文件存在证据，不是正确性验收。
- 工作台初始化于 2026-09-12 经独立验收 ACCEPTED，控制塔复核后关闭 20260912-001；证据见 [任务记录](tasks/20260912-001-workbench-init.md)。仅接受本地文档交接，不代表业务运行或发布通过。
- 初始化关闭时无活动任务；此项是历史快照。20260912-002 已完成独立验收并由控制塔关闭；远程治理任务 20260914-003 已完成并关闭。当前活动任务及下一步以 [当前任务](CURRENT_TASK.md) 及其任务文件为准。
- 2026-09-13 已将此前 11 项工作台文档改动原样提交为 78165c8112779701cd3ace8c9cca88c9576a315d；产品基线未改变。后续需求整理及远程持久化结果记录在 [当前任务文件](tasks/20260912-002-system-requirements.md)，不能用本地提交代替推送证据。
- 2026-09-14 远程 Git 治理任务已获用户确认，清理范围、保留项和远程核对标准记录在 [治理任务文件](tasks/20260914-003-remote-git-governance.md)；执行中不改写历史、不删除项目源代码或安全发布规则。
- 2026-09-14 远程 Git 治理已完成：远程仅保留 `main`、`codex/workbench-init` 和 `integration/freqtrade-dry-run`；Dependabot 配置已从 `main` 移除，项目源代码、测试和安全/发布文档保留。详细证据见治理任务文件。
- 2026-09-17 `20260912-002` 已由控制塔关闭：其 1.0 候选验证入口通过独立验收；未启动 Dry-run、未连接交易所、未读取真实凭据，不能据此推断策略盈利或实盘可用。
- 2026-09-18 `20260917-005` 经三项安全返工和第二次独立验收后由控制塔关闭；本地验收基线为分支 `codex/workbench-init`、HEAD `ba8738fe18289398a8c6713772416facddb5532d`，未提交或推送现有工作区修改。

## 静态文档与配置声明

- [README](../../README.md) 将项目定位为初始化阶段安全内核，未具备实盘条件；后续路线图不是已确认活动任务。
- 当前活动任务为 `20260918-006 / IN_PROGRESS`，负责把已验收的候选验证和单正式 Dry-run 监督/Web 基线从受保护的本地脏工作区迁移到最新 `main` 的一个受治理 PR；实施分支为 `codex/13-accepted-baseline-integration`，基线 `d524b1218746133410c409134749fe7058ddf3b2`；详见[当前任务](CURRENT_TASK.md)。`20260916-004` 仍为 `DRAFT`，不自动启动。
- [架构](../architecture.md) 描述研究、发布、执行、风控、审计的计划边界，不证明已全部实现。
- [pyproject.toml](../../pyproject.toml) 声明 Python >=3.12、空生产依赖、开发依赖 pytest/ruff、hatchling 构建。
- [.github/workflows/ci.yml](../../.github/workflows/ci.yml) 配置 Python 3.12，依次执行 python -m pip install -e '.[dev]'、ruff check .、pytest；本地独立验收另行执行了对应质量检查，不能替代远程 CI 状态。
- [安全模型](../safety-model.md) 与 [发布政策](../governance/RELEASE_POLICY.md) 是约束，不是现场合规或有效授权证据。配置示例不是真实发布清单。

## 未确认与限制

2026-09-18 独立验收使用 Python 3.12.10、项目 `.venv`、Freqtrade 2026.8 和开发依赖；全量 pytest 为 `46 passed`，Ruff、pip check、compileall、`git diff --check` 均通过。该证据只覆盖本地验收基线，不代表远程 CI、持续运行、真实交易或现场状态。

Playwright Python/Node 包不可用，未完成视觉验收。未启动正式 Dry-run 或交易服务，未连接交易所，未下载行情，未读取真实凭据或账户导出；不验证或授权实盘，也不能据此推断盈利。

初始化时没有 migration 交接记录；不能据此推断历史对话中没有未交接事项。共享流程入口依赖父工作区文件；换机缺失时须先恢复共享规范。

## 推断与建议

现有静态材料与独立验收足够接受本地文档工作台，不足以接受业务运行结果。后续需求、未决冲突及责任以 [当前任务](CURRENT_TASK.md) 指向的任务文件为准。2026-09-13 的文档提交与推送授权不扩大原验收范围，不自动开展业务开发；安全冲突解决前仍执行现行规则。
