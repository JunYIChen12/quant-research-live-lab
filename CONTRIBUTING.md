# Contributing

## 工作流

1. 策略、风控、核算、下单或运行配置变更先创建 Issue。
2. 从 main 创建短生命周期分支。
3. 小步提交，提交信息说明意图。
4. 运行 ruff check . 与 pytest。
5. 通过 Pull Request 合并；不要直接修改受保护的 main。

拼写修正、小型文档调整和 Dependabot 更新可以不建 Issue，但仍须通过 Pull Request。

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
