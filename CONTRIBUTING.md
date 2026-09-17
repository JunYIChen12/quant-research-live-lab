# Contributing

## 工作流

1. 策略、风控、核算、下单或运行配置变更先创建 Issue。
2. 使用 Issue 评论 `/transition STATE` 推进状态；不要直接修改 `status:*` 标签。
3. Issue 达到 `READY` 后，从 main 创建包含 Issue 编号的短生命周期分支。
4. 小步提交，提交信息说明意图；开发阶段可以创建 Draft Pull Request。
5. 运行 ruff check . 与 pytest。
6. 默认由可信协作者在 Issue 记录 `/verify PASS <完整 HEAD SHA>`，再进入 `ACCEPTED`；个人仓库只有在明确采用 solo 模式时，才由仓库所有者记录 `/verify SOLO PASS <完整 HEAD SHA> EVIDENCE <可复核引用>`。引用只允许当前仓库的 GitHub `issues`、`pull`、`commit` 或 `blob` 路径，或完整的 `codex://review?pr=<URL编码的当前PR URL>&path=<仓库相对路径>&line=<正整数>&side=left|right`。solo 记录是 owner attestation，不是另一位人工审核者；机器人、普通说明和实施线程自评不能代替结构化证据。新提交会使旧验收失效。
7. 通过 Pull Request 合并；不要直接修改受保护的 main。

拼写修正、小型文档调整和 Dependabot 更新可以不建 Issue，但仍须通过 Pull Request。
治理、安全、Actions 和运行规则变更不属于小型文档例外。

## Pull Request 要求

涉及交易逻辑、风险参数、订单状态、数据核算或 GitHub Actions 的变更必须包含：

- 对应测试；
- 风险与失败方式；
- 回滚方法；
- 是否影响资金、杠杆、持仓或止损；
- 证据或复现实验链接。

任何扩大风险的变更不能由自动化自行合并或部署。

## 发布变更

候选版本与实盘版本必须遵循 docs/governance/RELEASE_POLICY.md。PR 合并不等于允许运行；只有匹配的发布清单、带注释标签和 release-approved 标记全部通过校验后，运行时闸门才可放行。

## 敏感信息

不要在提交、Issue、PR、测试夹具或截图中放入 API Key、Secret、账户 ID、订单 ID、账户余额、实盘数据库和原始日志。发现泄露时请立即撤销并轮换凭证，再按 SECURITY.md 报告。
