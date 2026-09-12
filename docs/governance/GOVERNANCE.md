# Governance

Git is the source of truth for rules, code, tests and approval history. Chat messages, local notes and generated reports are proposals until they enter the repository through the required workflow.

## Change classes

| Class | Scope | Issue required | Release approval |
| --- | --- | --- | --- |
| L0 | Spelling, small documentation edits, Dependabot | No | No |
| L1 | Research and data-processing code | Yes | No |
| L2 | Accounting, order state, risk or dry-run behavior | Yes | Candidate release |
| L3 | Live strategy, capital, leverage, positions or loss limits | Yes | Live release |

Automation may reject, pause, stop or reduce risk. It may never grant an L3 approval or enlarge risk.

## Authority

1. AGENTS.md contains non-negotiable repository-wide constraints.
2. This governance policy defines how changes become authoritative.
3. Release policy defines how a merged commit becomes runnable.
4. Code and configuration implement those approved rules.
5. Runtime logs are evidence, not authority to change a running strategy.

Contradictions fail closed and must be resolved by a new Pull Request.
