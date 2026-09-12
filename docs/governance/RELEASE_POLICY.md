# Release Policy

Merging a Pull Request does not authorize dry-run or live execution.

## Release identity

A runnable release consists of four matching objects:

1. A commit merged into main through the recorded Pull Request.
2. An annotated Git tag pointing at that exact commit.
3. An external machine-readable release manifest deployed beside the artifacts.
4. The strategy, risk configuration and evidence bundle named in the manifest.

The manifest is generated after merge so it can contain the final commit SHA. It is a deployment artifact and must not be edited in place. Real manifests are ignored by Git; only the example is committed.

## Naming

- Dry-run tags: candidate-vMAJOR.MINOR.PATCH
- Live tags: live-vMAJOR.MINOR.PATCH

A candidate tag never authorizes live execution. Promotion to live requires a new approval decision and a live tag.

## Required manifest fields

- Release ID and execution mode.
- Approved commit SHA and release tag.
- Repository and approving Pull Request number.
- Required release-approved label.
- SHA-256 and relative path for strategy, risk configuration and evidence bundle.

## Runtime checks

Before startup and before any new order, the adapter must obtain a successful ReleaseVerification and combine it with the account and risk checks.

Verification fails closed when:

- HEAD differs from the approved commit.
- Tracked files are dirty.
- The annotated tag is missing, malformed or points elsewhere.
- Requested mode differs from the manifest mode.
- Any artifact is missing, outside the artifact root or has a different SHA-256.
- The approval Pull Request is not merged into main at the approved commit.
- The release-approved label is missing or the GitHub check cannot be completed.

## GitHub protection

Protect main with required Pull Requests, CI, resolved conversations, no force push and no deletion. Add tag rulesets for candidate-v* and live-v* so release identities cannot be silently moved or deleted.

For the current solo-maintainer stage, release-approved is a deliberate manual release action after merge. When a trusted second maintainer exists, L3 releases must also require independent approval.

## Rollback

Rollback creates a new release pointing to a previously reviewed commit. Do not move or reuse an existing release tag. Record the incident, the selected prior commit and a new approval Pull Request.
