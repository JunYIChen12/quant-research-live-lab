# Quant Research Live Lab

本项目用可复现的量化策略实验，减少情绪化交易对决策的影响。

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
