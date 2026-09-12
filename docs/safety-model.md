# Safety Model

## Invariants

- Leverage equals 1; any other value is treated as a mismatch.
- Margin mode is isolated.
- At most one position may be open.
- Strategy source and configuration are immutable for an approved run.
- Evidence and human approval are mandatory, not advisory metadata.
- Loss includes realized PnL, unrealized PnL, expected closing fees and adverse slippage.

## Braking

A single position mismatch pauses new orders and triggers reconciliation. A persistent mismatch, missing stop order, risk-limit breach, stale market data or uncertain account state escalates to emergency handling. Closing behavior must be idempotent and separately tested before live integration.

## Non-goals

The first version does not optimize strategies, approve releases, hold secrets, or submit exchange orders.
