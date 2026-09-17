# Recommended GitHub Settings

Configure after the first push:

- Protect main; block force pushes and deletion.
- Require Pull Requests, resolved conversations and the unique test status check.
- Before the governance bootstrap Pull Request is merged, do not require the `governance` commit status; its workflow must fail closed because `main` has no trusted checker yet.
- After that Pull Request is merged, verify the workflow is running from `main`, then require the exact `governance` commit status in branch protection. Record the settings change and a successful post-merge PR check before treating it as enforced.
- Dismiss stale approvals; require review by someone other than the last pusher when collaborators exist.
- Set default GITHUB_TOKEN permissions to read-only.
- Enable Dependabot alerts, secret scanning, push protection and CodeQL default setup.
- Enable Private Vulnerability Reporting.
- Prevent GitHub Actions from creating or approving Pull Requests unless a reviewed workflow explicitly needs it.
- Add tag rulesets that prevent update or deletion of candidate-v* and live-v*.
- Create the release-approved label; apply it manually only after the release decision.
- Create the task labels documented in `docs/governance/GOVERNANCE.md`; status labels are changed through `/transition STATE`, not by direct manual edits.
