# Repository Instructions

These rules apply to all automated agents and contributors.

1. Never read, create, print, or commit real exchange credentials or account exports.
2. Keep research, dry-run, and live execution data stores physically separate.
3. A live candidate requires a frozen commit, complete evidence, and explicit human approval.
4. Automation may reduce risk or stop execution; it may not increase capital, leverage, position count, symbol scope, or loss limits.
5. Gates fail closed. Missing, stale, contradictory, or unverified state blocks new orders.
6. Every risk or order-state change requires tests, failure analysis, and rollback notes.
7. Never claim profitability from in-sample results or a small number of live trades.
8. Do not add live exchange adapters until a separate reviewed milestone explicitly authorizes them.

## Codex Workflow

Start with [WORKFLOW.md](docs/codex/WORKFLOW.md), [PROJECT_STATE.md](docs/codex/PROJECT_STATE.md), [TASKS.md](docs/codex/TASKS.md), and [CURRENT_TASK.md](docs/codex/CURRENT_TASK.md), then read the referenced task and unabsorbed migration records. Verify cwd, branch, HEAD, and existing changes before acting. Keep cross-thread facts and evidence in the repository. Follow the single-writer and independent-verification gates; never skip READY. These workflow records do not replace the safety rules above or the existing contribution and release policies.
