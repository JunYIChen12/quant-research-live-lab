# BTC 趋势策略开发区间基线

## 结论

`BtcTrendBaseline` 在开发区间的历史回测收益为正，但证据不足且回撤过高，当前结论为
`RESEARCH_ONLY`。不得据此进入 Dry-run、实盘或宣称未来能够盈利。

## 固定条件

- 引擎：Freqtrade `2026.8`
- 数据：OKX 公共 BTC/USDT 现货 4 小时 K 线，共 8,999 根
- 请求区间：`2020-01-01` 至 `2024-01-01`
- 有效回测区间：`2020-02-03 08:00:00` 至 `2024-01-01 00:00:00`
- 策略：EMA50 上穿 EMA200 入场，下穿离场
- 约束：只做多、无杠杆、最多一个持仓
- 初始模拟资金：`1,000 USDT`
- 仓位：每次使用可用资金
- 手续费：每次成交 `0.1%`
- 未模拟：滑点、市场冲击和真实订单未成交

Binance 公共 API 在当前服务器经代理和直连均不可达；Kraken 可达但 Freqtrade 不支持直接
下载其历史 K 线。为避免逐笔下载多年成交，按用户授权改用可直接下载 K 线的 OKX 公共数据。

## 回测结果

| 指标 | 结果 |
|---|---:|
| 总交易数 | 18 |
| 胜 / 负 | 9 / 9 |
| 胜率 | 50.0% |
| 总收益 | 729.36% |
| 最终余额 | 8,293.579 USDT |
| 同期市场变化 | 352.82% |
| Profit factor | 2.52 |
| Mean profit p-value | 0.2711 |
| 最差单笔 | -19.34% |
| 已平仓口径最大回撤 | 51.67% |
| 钱包口径最大回撤 | 58.83% |
| 期末强制平仓贡献 | 297.09% |

## 判断

- 正面事实：开发区间扣除所设手续费后收益为正，并高于同期市场变化。
- 主要反证：只有 18 笔交易，`p=0.2711`，不足以排除偶然性。
- 风险问题：最大回撤超过 50%，不适合作为可执行候选。
- 结果偏差：总收益包含期末仍开放仓位的强制平仓，且未模拟滑点。
- 下一步边界：策略规则保持冻结；只有独立时间区间、成本压力和回撤检查通过后，才讨论
  Dry-run。当前不做参数搜索。

## 复现命令

```powershell
freqtrade download-data --config experiments/btc_trend/config.backtest.json `
  --userdir experiments/btc_trend/user_data --pairs BTC/USDT --timeframes 4h `
  --timerange 20200101-20240101 --data-format-ohlcv feather

freqtrade backtesting --config experiments/btc_trend/config.backtest.json `
  --userdir experiments/btc_trend/user_data `
  --strategy-path experiments/btc_trend/strategies --strategy BtcTrendBaseline `
  --timeframe 4h --timerange 20200101-20240101 --fee 0.001 `
  --export trades --backtest-directory experiments/btc_trend/backtest_results
```

行情数据与原始回测制品位于 Git 忽略目录，不提交仓库。
