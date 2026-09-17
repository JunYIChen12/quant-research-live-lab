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

## Task lifecycle

GitHub Issue is the formal task and state record. `docs/codex` may keep detailed thread ownership, commands, evidence and handoffs, but it does not override the Issue state.

The supported lifecycle is:

`DRAFT -> ANALYZING -> READY -> IN_PROGRESS -> READY_FOR_VERIFY -> ACCEPTED -> CLOSED`

Verification failures use `REWORK -> IN_PROGRESS`. Missing facts, permissions or environment use `BLOCKED -> ANALYZING`. Request a transition by commenting `/transition STATE` on the Issue; direct edits to `status:*` labels are not a governed transition.

The gate checks:

- `READY`: goal, scope, excluded scope, acceptance criteria, risk and rollback exist.
- `IN_PROGRESS`: the Issue has an assignee and an Issue-linked branch exists.
- `READY_FOR_VERIFY`: an open linked Pull Request exists.
- `ACCEPTED`: an independent approval or `/verify PASS <full-head-sha>` record matches the current Pull Request HEAD.
- `CLOSED`: a code task has a merged Pull Request; an analysis-only task has a recorded close conclusion.

Draft Pull Requests may be created during implementation. The `governance` commit status remains pending until the Issue reaches `ACCEPTED`; passing CI alone does not authorize merge or runtime execution.

After independent verification, a trusted collaborator records the exact reviewed commit with `/verify PASS <full-head-sha>`, then requests `/transition ACCEPTED`. A later commit makes the old verification stale and returns the governance status to pending.

L0 spelling and small documentation fixes may omit an Issue, but still require a Pull Request and CI. Changes to governance, security, Actions or runtime rules are never L0.
