# 项目状态

## 已核对基线

- 核对日期：2026-09-13；唯一目录 D:/CodexProjects/projects/quant-research-live-lab。
- 产品基线：a5fdc77ccb54f5d4d3d704bf4a78cb0166942c28；初始化任务分支 codex/workbench-init。动态状态每次以 Git 与 [当前任务](CURRENT_TASK.md) 重新核对。
- origin：https://github.com/JunYIChen12/quant-research-live-lab.git；2026-09-13 使用 git ls-remote 核对，默认分支及 main 仍为上述产品基线，写入前远程无 codex/workbench-init 分支。此次只获准推送该工作分支，不直接更新 main。
- 本次本地工具环境：Windows、PowerShell 7.6.5；没有安装或重建环境。
- 仓库存在 src/quant_lab/gates.py、release.py 及对应 tests/test_gates.py、test_release.py；这是文件存在证据，不是正确性验收。
- 工作台初始化于 2026-09-12 经独立验收 ACCEPTED，控制塔复核后关闭 20260912-001；证据见 [任务记录](tasks/20260912-001-workbench-init.md)。仅接受本地文档交接，不代表业务运行或发布通过。
- 初始化关闭时无活动任务；此项是历史快照。当前为 20260914-003 / IN_PROGRESS，由 00｜项目控制塔负责；远程治理完成后恢复 20260912-002 / ANALYZING。动态任务、冲突和下一步以 [当前任务](CURRENT_TASK.md) 及任务文件为准。
- 2026-09-13 已将此前 11 项工作台文档改动原样提交为 78165c8112779701cd3ace8c9cca88c9576a315d；产品基线未改变。后续需求整理及远程持久化结果记录在 [当前任务文件](tasks/20260912-002-system-requirements.md)，不能用本地提交代替推送证据。
- 2026-09-14 远程 Git 治理任务已获用户确认，清理范围、保留项和远程核对标准记录在 [治理任务文件](tasks/20260914-003-remote-git-governance.md)；执行中不改写历史、不删除项目源代码或安全发布规则。

## 静态文档与配置声明

- [README](../../README.md) 将项目定位为初始化阶段安全内核，未具备实盘条件；后续路线图不是已确认活动任务。
- [架构](../architecture.md) 描述研究、发布、执行、风控、审计的计划边界，不证明已全部实现。
- [pyproject.toml](../../pyproject.toml) 声明 Python >=3.12、空生产依赖、开发依赖 pytest/ruff、hatchling 构建。
- [.github/workflows/ci.yml](../../.github/workflows/ci.yml) 配置 Python 3.12，依次执行 python -m pip install -e '.[dev]'、ruff check .、pytest。命令来源已核对，本轮未执行。
- [安全模型](../safety-model.md) 与 [发布政策](../governance/RELEASE_POLICY.md) 是约束，不是现场合规或有效授权证据。配置示例不是真实发布清单。

## 未确认与限制

Python、本地依赖、测试结果、CI 实际结果、远程保护、运行进程、数据存储隔离和现场状态均 UNKNOWN。本轮不读取凭据或账户导出，不连接交易所，不验证或授权实盘。

初始化时没有 migration 交接记录；不能据此推断历史对话中没有未交接事项。共享流程入口依赖父工作区文件；换机缺失时须先恢复共享规范。

## 推断与建议

现有静态材料与独立验收足够接受本地文档工作台，不足以接受业务运行结果。后续需求、未决冲突及责任以 [当前任务](CURRENT_TASK.md) 指向的任务文件为准。2026-09-13 的文档提交与推送授权不扩大原验收范围，不自动开展业务开发；安全冲突解决前仍执行现行规则。
