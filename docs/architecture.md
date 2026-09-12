# Architecture

## Two isolated loops

The research loop produces immutable candidate artifacts from historical data, backtests, out-of-sample validation, and leakage checks. The execution loop consumes one approved artifact, records real-world costs and anomalies, and returns observations to research.

Execution observations never mutate the running strategy. Any change creates a new version that repeats the full validation path.

## Planned boundaries

- research: data preparation, hypotheses, backtests and validation.
- release: evidence manifest, commit/config digests and human approval.
- execution: dry-run or live adapter consuming a frozen release.
- risk: preflight, per-order gates, circuit breakers and kill switch.
- audit: append-only decisions, fills, fees, funding, slippage and incidents.

Adapters depend on the safety kernel; the safety kernel must not depend on an exchange SDK.
