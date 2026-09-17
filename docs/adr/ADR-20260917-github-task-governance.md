# ADR-20260917 GitHub 任务治理

## 背景

项目同时使用 GitHub Issue/PR 和 `docs/codex` 记录任务。此前两者没有稳定映射，已出现本地任务状态、项目状态和正式 GitHub 交付状态不同步的问题。

## 候选方案

1. 继续只依靠 Markdown 和人工检查，成本最低但不能自动阻止非法流转。
2. 自建任务数据库或管理平台，可以强制状态但重复 GitHub 能力，维护成本过高。
3. 使用 GitHub Issue 作为正式状态源，`docs/codex` 保存执行证据，并用一个标准库脚本和一个 Actions 工作流检查状态和 PR。

## 决定

采用方案 3。正式任务状态使用 `status:*` 标签，通过 Issue 评论 `/transition STATE` 请求流转。代码任务使用 Draft PR 提前运行 CI；治理提交状态在独立验收前保持 `pending`。默认多人验收记录必须用 `/verify PASS <完整 HEAD SHA>` 绑定准确提交。个人仓库可由所有者显式选择 `/verify SOLO PASS <完整 HEAD SHA> EVIDENCE <可复核引用>`；引用只允许当前仓库的 GitHub `issues`、`pull`、`commit` 或 `blob` 路径，或完整的 `codex://review?pr=<URL编码的当前PR URL>&path=<仓库相对路径>&line=<正整数>&side=left|right`。该记录是 owner attestation，不伪装成另一位人工审核者。GitHub 无法证明 Codex 线程独立性，因此结构化证据引用是可复核要求，而不是自动证明。代码任务只能由匹配的合并 PR `closed` 事件关闭；Issue 进入 `ACCEPTED` 后才变为 `success`，后续新提交自动使旧验收失效。

`docs/codex` 不再独立决定正式状态，只记录责任线程、详细证据、失败和交接。两者冲突时以 GitHub Issue 为准；GitHub 状态无法核对时失败关闭。

## 未采用原因

- 纯人工规则已经发生状态漂移。
- 自建平台会复制 Issue、PR、Actions 和分支保护，不符合首版最小原则。

## 影响

- 非 L0 工作必须有关联 Issue。
- 状态变化由治理工作流检查；直接修改标签不属于受支持的流转方式。
- 自动化只能检查证据存在和状态顺序，不能代替用户确认、独立验收、solo owner attestation 的明确选择、Dry-run 或实盘授权。
- 仓库管理员仍具有平台级权限；治理目标是阻止普通流程误操作，不声称能限制仓库所有者的恶意绕过。

## 验证

- 单元测试覆盖合法和非法流转、READY 完整性、实施责任、PR 关联、独立验收、关闭条件和 L0 例外。
- Pull Request 上同时运行现有 `test` 和新的 `governance` 提交状态。

## 回滚

通过新 Pull Request 删除治理工作流、脚本、模板和状态标签，并从 `main` 必需检查中移除 `governance`。不直接绕过分支保护修改正式分支。
