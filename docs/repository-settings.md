# Recommended GitHub Settings

Configure after the first push:

- Protect main; block force pushes and deletion.
- Require Pull Requests, resolved conversations and the unique test status check.
- Dismiss stale approvals; require review by someone other than the last pusher when collaborators exist.
- Set default GITHUB_TOKEN permissions to read-only.
- Enable Dependabot alerts, secret scanning, push protection and CodeQL default setup.
- Enable Private Vulnerability Reporting.
- Prevent GitHub Actions from creating or approving Pull Requests unless a reviewed workflow explicitly needs it.
- Add tag rulesets that prevent update or deletion of candidate-v* and live-v*.
- Create the release-approved label; apply it manually only after the release decision.
