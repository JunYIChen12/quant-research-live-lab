# 项目任务工作流

共享规范：[Codex 多线程任务流转规范](../../../../docs/codex/WORKFLOW.md)，实际位置 D:/CodexProjects/docs/codex/WORKFLOW.md。本文件是项目入口，不修改共享规范；共享文件不可访问或规则冲突时停止流转并报告，不猜测恢复。

## 启动顺序

1. 核对当前绝对路径、Git 分支、HEAD、状态与远程仓库，以及父级和当前目录适用的 AGENTS.md。
2. 阅读本文件、[项目状态](PROJECT_STATE.md)、[任务索引](TASKS.md)、[当前任务](CURRENT_TASK.md)。
3. 阅读 [migration](migration/README.md) 中尚未吸收的记录与当前任务指向的文件。目录说明不是交接记录。
4. 核对唯一状态、负责人、白名单与下一步；没有经用户确认的任务时保持“当前无活动任务”，不从路线图自动创建任务。

## 角色与状态

控制塔登记、流转和关闭；分析默认只读；实施是唯一默认写入者；验收独立、默认只读且不自行修复。任务文件记录当次角色安排、基线、事实、推断、决定、命令、结果和跳过项；索引只保留编号、标题、状态、路径，指针保留当前责任人和下一步。

正常流转：DRAFT -> ANALYZING -> READY -> IN_PROGRESS -> READY_FOR_VERIFY -> ACCEPTED -> CLOSED。
分析、实施或验收遇到关键事实、权限或环境不足时记录 BLOCKED；验收失败为 REWORK，返工再进入 IN_PROGRESS。恢复前重新核对阻塞原因与任务契约，不跳过 READY。

控制塔仅在独立验收证据充分后关闭，更新稳定项目事实；无下一项已确认任务时，当前任务指针写“当前无活动任务”。[decisions](decisions/README.md) 保存长期决定，[archive](archive/README.md) 保存关闭记录。

## 安全与变更

[项目安全规则](../../AGENTS.md)、[贡献要求](../../CONTRIBUTING.md)、[治理政策](../governance/GOVERNANCE.md) 和 [发布政策](../governance/RELEASE_POLICY.md) 保持适用。文档落地、自测、独立验收、PR 合并均不等于实盘授权。稳定流程规则变更须说明解决的重复问题并更新 [CHANGELOG](../../CHANGELOG.md)，没有事故证据不得编造。
