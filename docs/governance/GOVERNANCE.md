# Governance

Git is the source of truth for rules, code, tests and approval history. Chat messages, local notes and generated reports are proposals until they enter the repository through the required workflow.

## Change classes

| Class | Scope | Issue required | Release approval |
| --- | --- | --- | --- |
| L0 | Spelling, small documentation edits, Dependabot | No | No |
| L1 | Research and data-processing code | Yes | No |
| L2 | Accounting, order state, risk or dry-run behavior | Yes | Candidate release |
| L3 | Live strategy, capital, leverage, positions or loss limits | Yes | Live release |

The governance checker derives the class from Pull Request paths. L0 is the existing
small-documentation exception. L1 is limited to `src/quant_lab/**` and ordinary
`tests/**` paths, excluding release, validation, Dry-run and risk-gate files. L2,
L3, governance, security, Actions, configuration and every unknown or mixed path
are high risk and fail closed.

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

An explicitly classified L1 change may use the compact path
`DRAFT`/`ANALYZING`/`READY -> IN_PROGRESS -> READY_FOR_VERIFY -> ACCEPTED -> CLOSED`.
The compact entry requires an assigned Issue, an Issue-linked branch and an open
Pull Request whose changed files classify as L1. High-risk and unclassified
changes must use the complete lifecycle above.

The gate checks:

- `READY`: goal, scope, excluded scope, acceptance criteria, risk and rollback exist.
- `IN_PROGRESS`: the Issue has an assignee and an Issue-linked branch exists.
- `READY_FOR_VERIFY`: an open linked Pull Request exists.
- `ACCEPTED`: the default path requires an independent approval or `/verify PASS <full-head-sha>` record from a trusted collaborator that matches the current Pull Request HEAD. A personal repository may explicitly choose the solo path with `/verify SOLO PASS <full-head-sha> EVIDENCE <reviewable-reference>`; the reference must be a current-repository GitHub `issues`, `pull`, `commit` or `blob` path, or the exact `codex://review?pr=<URL-encoded-current-PR-URL>&path=<repository-relative-path>&line=<positive-integer>&side=left|right` form. This is an owner attestation, not a second human reviewer.
- `CLOSED`: a code task is closed only by the matching merged Pull Request `closed` event with a non-empty `merge_commit_sha`, current accepted verification and no other open linked Pull Request. Manual `/transition CLOSED` and historical merged Pull Request scans do not close code tasks; an analysis-only task retains its recorded close-conclusion exception.

Draft Pull Requests may be created during implementation. The `governance` commit status remains pending until the Issue reaches `ACCEPTED`; passing CI alone does not authorize merge or runtime execution. Non-UI changes do not require Playwright or visual checks. Historical test-count differences are warnings unless the current HEAD lacks a required test or CI fails.

When the default branch gains a new acceptance command, use a two-step migration. First, independently verify the compatibility Pull Request and obtain explicit owner authorization to merge it; the compatibility Pull Request may be merged only as a migration step, not by direct label edits or a fabricated reviewer. Second, after the compatibility Pull Request is merged and the new `main` is authoritative, create a minimal activation/closure Pull Request for the same Issue. The new `main` must then process that open Pull Request through the complete `verify -> ACCEPTED -> merge -> CLOSED` path. Do not directly edit `status:*` labels or impersonate/fabricate an independent reviewer.

The first governance Pull Request is a bootstrap exception: when `main` has no trusted checker, its governance workflow fails closed and never uses the Pull Request's checker to create a success proof. Merge it only through the existing ordinary required checks. After merge, verify the workflow from `main`, enable `governance` as a required status, and record that repository setting change.

After independent verification, a trusted collaborator records the exact reviewed commit with `/verify PASS <full-head-sha>`, then requests `/transition ACCEPTED`. For the explicit solo path, the repository owner records the exact reviewed commit and a structured evidence reference with `/verify SOLO PASS <full-head-sha> EVIDENCE <reviewable-reference>`. GitHub cannot prove that a Codex thread is independent, so the record must be described as owner attestation; implementation-thread self-assessment, ordinary explanations and bots do not satisfy it. The default multi-person rule never falls back to solo automatically. A later commit makes either verification record stale and returns the governance status to pending.

L0 spelling and small documentation fixes may omit an Issue, but still require a Pull Request and CI. Changes to governance, security, Actions or runtime rules are never L0. Issue/PR is the authoritative task record; `docs/codex` records only stable facts, decisions and necessary handoffs.
