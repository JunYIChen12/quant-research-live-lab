# Quant Research Live Lab

本项目的长期目标是用可重复、可检查的量化研究与规则执行，减少情绪对交易决策的影响；不承诺盈利。

## 项目文档

- [整体用户需求](docs/USER_REQUIREMENTS.md)：项目目标、研究到交易的阶段和边界。
- [当前状态](docs/STATUS.md)：目前已完成什么、现在是否有获批中的研究任务。
- [项目历史](docs/PROJECT_HISTORY.md)：项目初衷、方向变化和已有研究证据的来历。

## 已有研究证据

BTC 趋势实验均保留在 [`experiments/btc_trend/`](experiments/btc_trend/)；包括基线、留出区间、固定结束日期和候选比较。失败或未达标准的结果作为历史证据保留，不代表后续研究方向。

## 安全边界

- 不提交交易所凭据、账户导出、原始行情或交易数据库。
- 回测和少量交易不构成盈利证明或投资建议。
- 未经单独批准，不启动 Dry-run、实盘或交易所账户访问。

## 本地检查

```powershell
python -m pip install "freqtrade==2026.8" "pytest>=8.3,<9" "ruff>=0.9,<1"
ruff check .
python -m pytest
```

## License

Apache-2.0，详见 [LICENSE](LICENSE)。