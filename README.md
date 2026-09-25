# Quant Research Live Lab

本项目希望用预先确定的规则减少情绪化交易。研究方向是以可复现、边界明确的信号研究寻找策略候选，而不只依赖人逐个提出完整买卖策略；所有候选和失败尝试都应保留。

这是一项待验证的研究方法假设，不是盈利保证。当前聚焦 BTC 时间序列信号；新研究批次须先在 GitHub Issue 中固定范围与验收标准，获批前不启动搜索或优化。项目初衷和方向演变见 [PROJECT_HISTORY.md](PROJECT_HISTORY.md)。

当前只研究策略是否值得继续验证，不运行真实 Dry-run，不连接交易账户，也不承诺盈利。

## 当前阶段

- 研究对象：BTC/USDT 现货，4 小时周期。
- 基线策略：EMA50 与 EMA200 趋势交叉。
- 当前结论：`RESEARCH_ONLY`。
- 当前基线已完成固定结束日期验证并停止继续投入；新策略假设需另立任务批准。
- Donchian 55/20 与 SMA200 趋势过滤均因最大回撤超过 25% 而淘汰，批次终态为 `EXHAUSTED`。

项目起因和发展过程见 [PROJECT_HISTORY.md](PROJECT_HISTORY.md)，当前唯一工作目标见
[NOW.md](NOW.md)。

## 本地检查

```powershell
python -m pip install "freqtrade==2026.8" "pytest>=8.3,<9" "ruff>=0.9,<1"
ruff check .
python -m pytest
```

## 安全边界

- 不提交交易所密钥、账户导出、原始行情或交易数据库。
- 研究结果不等于未来盈利，也不构成投资建议。
- 未经单独批准，不启动 Dry-run、实盘或交易所账户访问。

## License

Apache-2.0，详见 [LICENSE](LICENSE)。
