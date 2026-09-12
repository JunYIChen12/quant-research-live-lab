# Contributing

## 工作流

1. 从 main 创建短生命周期分支。
2. 小步提交，提交信息说明意图。
3. 运行 ruff check . 与 pytest。
4. 通过 Pull Request 合并；不要直接修改受保护的 main。

## Pull Request 要求

涉及交易逻辑、风险参数、订单状态、数据核算或 GitHub Actions 的变更必须包含：

- 对应测试；
- 风险与失败方式；
- 回滚方法；
- 是否影响资金、杠杆、持仓或止损；
- 证据或复现实验链接。

任何扩大风险的变更不能由自动化自行合并或部署。

## 敏感信息

不要在提交、Issue、PR、测试夹具或截图中放入 API Key、Secret、账户 ID、订单 ID、账户余额、实盘数据库和原始日志。发现泄露时请立即撤销并轮换凭证，再按 SECURITY.md 报告。
