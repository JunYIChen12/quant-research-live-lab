from pathlib import Path

from tools.governance import (
    GitHubClient,
    PullRequestContext,
    TransitionContext,
    _is_small_documentation_change,
    _manual_label_change_detected,
    _valid_evidence_reference,
    _verification_passed,
    extract_linked_issue,
    handle_issue_closed,
    handle_issue_label_change,
    handle_pull_request,
    handle_transition,
    handle_verification,
    parse_solo_verification_command,
    parse_transition_command,
    parse_verification_command,
    status_from_labels,
    validate_pull_request,
    validate_transition,
)

READY_BODY = """
## 目标
建立自动门禁。

## 范围
状态流转和 PR 检查。

## 不在范围
不修改交易代码。

## 验收标准
非法流转必须失败。

## 风险与回滚
通过独立 PR 回退。
"""

SOLO_EVIDENCE = (
    "codex://review?pr=https%3A%2F%2Fgithub.com%2Fowner%2Frepo%2Fpull%2F10"
    "&path=tools%2Fgovernance.py&line=1&side=right"
)


def test_ready_requires_complete_issue_contract() -> None:
    errors = validate_transition("ANALYZING", "READY", TransitionContext(body="## 目标\n有目标"))

    assert errors == ["READY 缺少章节：范围、不在范围、验收标准、风险与回滚"]


def test_in_progress_cannot_skip_ready() -> None:
    context = TransitionContext(body=READY_BODY, assignees=("owner",), branch_exists=True)

    assert validate_transition("ANALYZING", "IN_PROGRESS", context) == [
        "非法状态流转：ANALYZING -> IN_PROGRESS"
    ]


def test_in_progress_requires_owner_and_branch() -> None:
    errors = validate_transition("READY", "IN_PROGRESS", TransitionContext(body=READY_BODY))

    assert errors == ["IN_PROGRESS 缺少责任人", "IN_PROGRESS 缺少任务分支"]


def test_ready_for_verify_requires_pull_request() -> None:
    errors = validate_transition(
        "IN_PROGRESS", "READY_FOR_VERIFY", TransitionContext(body=READY_BODY)
    )

    assert errors == ["READY_FOR_VERIFY 缺少关联 Pull Request"]


def test_acceptance_requires_independent_verification() -> None:
    errors = validate_transition(
        "READY_FOR_VERIFY",
        "ACCEPTED",
        TransitionContext(body=READY_BODY, open_pull_request=True),
    )

    assert errors == ["ACCEPTED 缺少独立验收通过记录"]


def test_code_task_closes_only_after_merge() -> None:
    errors = validate_transition("ACCEPTED", "CLOSED", TransitionContext(body=READY_BODY))

    assert errors == ["代码任务必须由准确的 Pull Request closed 事件关闭"]


def test_rework_returns_only_to_implementation() -> None:
    context = TransitionContext(body=READY_BODY, assignees=("owner",), branch_exists=True)

    assert validate_transition("REWORK", "IN_PROGRESS", context) == []
    assert validate_transition("REWORK", "READY", context) == [
        "非法状态流转：REWORK -> READY"
    ]


def test_ready_pull_request_requires_linked_ready_issue_and_sections() -> None:
    context = PullRequestContext(
        body="## 变更\n内容",
        draft=False,
        changed_files=("src/quant_lab/gates.py",),
        linked_issue_number=9,
        linked_issue_status="IN_PROGRESS",
    )

    assert validate_pull_request(context) == [
        "Pull Request 缺少章节：证据、风险与回滚、未验证事项、独立验收",
        "非 Draft Pull Request 要求关联 Issue 为 READY_FOR_VERIFY 或 ACCEPTED",
    ]


def test_l0_exception_only_allows_small_documentation_changes() -> None:
    allowed = PullRequestContext(
        body="- [x] L0 例外",
        draft=False,
        changed_files=("docs/typo.md",),
    )
    denied = PullRequestContext(
        body="- [x] L0 例外",
        draft=False,
        changed_files=("docs/governance/GOVERNANCE.md",),
    )

    assert validate_pull_request(allowed) == []
    assert validate_pull_request(denied) == ["L0 例外包含非小型文档变更"]


def test_transition_command_is_exact_and_case_insensitive() -> None:
    assert parse_transition_command("/transition ready") == "READY"
    assert parse_transition_command(" please /transition READY") is None
    assert parse_transition_command("/transition UNKNOWN") is None


def test_issue_must_have_at_most_one_status_label() -> None:
    assert status_from_labels(("enhancement", "status:ready")) == "READY"

    try:
        status_from_labels(("status:ready", "status:in-progress"))
    except ValueError as exc:
        assert str(exc) == "Issue 同时存在多个状态标签"
    else:
        raise AssertionError("multiple status labels must fail")


def test_linked_issue_uses_github_closing_keywords() -> None:
    assert extract_linked_issue("Closes #9") == 9
    assert extract_linked_issue("Fixes #12\nResolves #13") == 12
    assert extract_linked_issue("Related to #9") is None


class FakePullRequestClient:
    def __init__(self, issue_status: str, verified_sha: str | None = None) -> None:
        self.issue_status = issue_status
        self.verified_sha = verified_sha
        self.statuses: list[tuple[str, str, str]] = []

    def issue(self, number: int) -> dict[str, object]:
        assert number == 9
        label = f"status:{self.issue_status.lower().replace('_', '-')}"
        return {"number": 9, "labels": [{"name": label}]}

    def pull_request_files(self, number: int) -> tuple[str, ...]:
        assert number == 10
        return ("tools/governance.py",)

    def issue_comments(self, number: int) -> list[dict[str, str]]:
        assert number == 9
        if self.verified_sha is None:
            return []
        return [
            {
                "body": f"/verify PASS {self.verified_sha}",
                "author_association": "OWNER",
                "user": {"login": "verifier"},
            }
        ]

    def pull_request_reviews(self, number: int) -> list[dict[str, object]]:
        assert number == 10
        return []

    def pull_request_commits(self, number: int) -> list[dict[str, object]]:
        assert number == 10
        return [{"committer": {"login": "implementer"}}]

    def update_issue(self, number: int, **changes: object) -> None:
        assert number == 9

    def comment(self, number: int, body: str) -> None:
        assert number == 9

    def set_commit_status(self, sha: str, state: str, description: str) -> None:
        self.statuses.append((sha, state, description))


PR_EVENT = {
    "pull_request": {
        "number": 10,
        "body": """
Closes #9

## 变更
增加治理检查。

## 证据
测试通过。

## 风险与回滚
可以回退。

## 未验证事项
无。

## 独立验收
等待独立验收。
""",
        "draft": False,
        "head": {"sha": "a" * 40},
        "user": {"login": "implementer"},
    }
}


def test_ready_pull_request_stays_pending_until_issue_is_accepted() -> None:
    client = FakePullRequestClient("READY_FOR_VERIFY")

    assert handle_pull_request(PR_EVENT, client) == 0
    assert client.statuses == [("a" * 40, "pending", "等待独立验收通过")]


def test_accepted_issue_allows_governance_status_to_pass() -> None:
    client = FakePullRequestClient("ACCEPTED", verified_sha="a" * 40)

    assert handle_pull_request(PR_EVENT, client) == 0
    assert client.statuses == [("a" * 40, "success", "治理检查通过")]


def test_new_commit_invalidates_old_verification() -> None:
    client = FakePullRequestClient("ACCEPTED", verified_sha="b" * 40)

    assert handle_pull_request(PR_EVENT, client) == 0
    assert client.statuses == [("a" * 40, "pending", "等待当前提交的独立验收")]


def test_verification_command_binds_exact_head_sha() -> None:
    sha = "a" * 40

    assert parse_verification_command(f"/verify PASS {sha}") == sha
    assert parse_verification_command(f"/verify PASS {sha[:12]}") is None
    assert parse_verification_command(f"text /verify PASS {sha}") is None


def test_solo_verification_requires_structured_codex_evidence() -> None:
    sha = "a" * 40

    assert parse_solo_verification_command(
        f"/verify SOLO PASS {sha} EVIDENCE {SOLO_EVIDENCE}"
    ) == (sha, SOLO_EVIDENCE)
    assert parse_solo_verification_command(f"/verify SOLO PASS {sha}") is None


def test_evidence_reference_accepts_only_reviewable_repository_paths() -> None:
    repository = "owner/repo"
    accepted = (
        "https://github.com/owner/repo/issues/9",
        "https://github.com/owner/repo/pull/10",
        "https://github.com/owner/repo/commit/" + "a" * 40,
        "https://github.com/owner/repo/blob/main/tools/governance.py",
        SOLO_EVIDENCE,
    )
    rejected = (
        "https://?",
        "https://x",
        "https://github.com/other/repo/issues/9",
        "codex://x",
        "codex://thread/123",
        "codex://review?pr=https%3A%2F%2Fgithub.com%2Fowner%2Frepo%2Fpull%2F10",
        "codex://review?pr=https%3A%2F%2Fgithub.com%2Fowner%2Frepo%2Fpull%2F11"
        "&path=tools%2Fgovernance.py&line=1&side=right",
        "codex://review?pr=https%3A%2F%2Fgithub.com%2Fowner%2Frepo%2Fpull%2F10"
        "&path=../tools%2Fgovernance.py&line=1&side=right",
    )

    assert all(_valid_evidence_reference(value, repository, 10) for value in accepted)
    assert not any(_valid_evidence_reference(value, repository, 10) for value in rejected)


class FakeVerificationClient:
    def __init__(self) -> None:
        self.comments: list[str] = []
        self.statuses: list[tuple[str, str, str]] = []

    def issue(self, number: int) -> dict[str, object]:
        assert number == 9
        return {"number": 9, "labels": [{"name": "status:ready-for-verify"}]}

    def pull_requests(self) -> list[dict[str, object]]:
        return [
            {
                "number": 10,
                "state": "open",
                "body": PR_EVENT["pull_request"]["body"],
                "head": {"sha": "a" * 40},
                "user": {"login": "implementer"},
            }
        ]

    def comment(self, number: int, body: str) -> None:
        assert number == 9
        self.comments.append(body)

    def pull_request_files(self, number: int) -> tuple[str, ...]:
        assert number == 10
        return ("tools/governance.py",)

    def pull_request_commits(self, number: int) -> list[dict[str, object]]:
        assert number == 10
        return [{"committer": {"login": "implementer"}}]

    def set_commit_status(self, sha: str, state: str, description: str) -> None:
        self.statuses.append((sha, state, description))

    def update_issue(self, number: int, **changes: object) -> None:
        assert number == 9

    def issue_comments(self, number: int) -> list[dict[str, object]]:
        return [
            {
                "body": f"/verify PASS {'a' * 40}",
                "author_association": "MEMBER",
                "user": {"login": "verifier"},
            }
        ]


class FakeSoloVerificationClient(FakeVerificationClient):
    repository = "owner/repo"

    def __init__(self) -> None:
        super().__init__()
        self.updates: list[dict[str, object]] = []

    def update_issue(self, number: int, **changes: object) -> None:
        assert number == 9
        self.updates.append(changes)


def test_solo_owner_attestation_is_explicit_and_records_mode() -> None:
    client = FakeSoloVerificationClient()
    sha = "a" * 40
    event = {
        "issue": {"number": 9},
        "comment": {
            "body": f"/verify SOLO PASS {sha} EVIDENCE {SOLO_EVIDENCE}",
            "author_association": "OWNER",
            "user": {"login": "owner"},
        },
    }

    assert handle_verification(event, client) == 0
    assert client.updates == [
        {
            "labels": [
                "status:ready-for-verify",
                "verification:passed",
            ]
        }
    ]
    assert client.comments == [
        "已记录当前 PR HEAD `" + sha + "` 的 solo owner attestation；"
        "Codex 证据引用：`" + SOLO_EVIDENCE + "`。"
    ]


def test_solo_verification_rejects_unreviewable_evidence() -> None:
    client = FakeSoloVerificationClient()
    sha = "a" * 40
    event = {
        "issue": {"number": 9},
        "comment": {
            "body": f"/verify SOLO PASS {sha} EVIDENCE codex://thread/123",
            "author_association": "OWNER",
            "user": {"login": "owner"},
        },
    }

    assert handle_verification(event, client) == 1
    assert client.updates == []
    assert client.comments == ["治理门禁拒绝：solo evidence 引用不可复核。"]


def test_solo_owner_attestation_is_bound_to_current_head() -> None:
    sha = "a" * 40

    class SoloEvidenceClient:
        repository = "owner/repo"

        def issue_comments(self, number: int) -> list[dict[str, object]]:
            return [
                {
                    "body": f"/verify SOLO PASS {sha} EVIDENCE {SOLO_EVIDENCE}",
                    "author_association": "OWNER",
                    "user": {"login": "owner"},
                }
            ]

        def pull_request_reviews(self, number: int) -> list[dict[str, object]]:
            return []

        def pull_request_commits(self, number: int) -> list[dict[str, object]]:
            return [{"committer": {"login": "implementer"}}]

    client = SoloEvidenceClient()
    pull = {"head": {"sha": sha}, "user": {"login": "implementer"}, "number": 10}

    assert _verification_passed(client, 9, pull)
    assert not _verification_passed(client, 9, {**pull, "head": {"sha": "b" * 40}})


def test_solo_owner_attestation_cannot_be_recorded_by_a_bot() -> None:
    sha = "a" * 40

    class BotEvidenceClient:
        repository = "owner/repo"

        def issue_comments(self, number: int) -> list[dict[str, object]]:
            return [
                {
                    "body": f"/verify SOLO PASS {sha} EVIDENCE {SOLO_EVIDENCE}",
                    "author_association": "OWNER",
                    "user": {"login": "owner[bot]", "type": "Bot"},
                }
            ]

        def pull_request_reviews(self, number: int) -> list[dict[str, object]]:
            return []

        def pull_request_commits(self, number: int) -> list[dict[str, object]]:
            return [{"committer": {"login": "owner[bot]"}}]

    pull = {"head": {"sha": sha}, "user": {"login": "implementer"}, "number": 10}

    assert not _verification_passed(BotEvidenceClient(), 9, pull)


def test_implementation_author_cannot_record_independent_verification() -> None:
    client = FakeVerificationClient()
    event = {
        "issue": {"number": 9},
        "comment": {
            "body": f"/verify PASS {'a' * 40}",
            "author_association": "OWNER",
            "user": {"login": "implementer"},
        },
    }

    assert handle_verification(event, client) == 1
    assert client.comments == ["治理门禁拒绝：实施者或最后推送者不能独立验收 Pull Request。"]


class FakeTransitionClient:
    def __init__(self) -> None:
        self.statuses: list[tuple[str, str, str]] = []
        self.pull_body = "Closes #9"

    def issue(self, number: int) -> dict[str, object]:
        assert number == 9
        return {
            "number": 9,
            "body": READY_BODY,
            "labels": [{"name": "status:ready-for-verify"}],
            "assignees": [{"login": "owner"}],
        }

    def pull_requests(self) -> list[dict[str, object]]:
        return [
            {
                "number": 10,
                "state": "open",
                "body": self.pull_body,
                "head": {"sha": "a" * 40},
                "user": {"login": "owner"},
                "merged_at": None,
            }
        ]

    def update_issue(self, number: int, **changes: object) -> None:
        assert number == 9

    def comment(self, number: int, body: str) -> None:
        assert number == 9

    def set_commit_status(self, sha: str, state: str, description: str) -> None:
        self.statuses.append((sha, state, description))

    def issue_comments(self, number: int) -> list[dict[str, object]]:
        return [
            {
                "body": f"/verify PASS {'a' * 40}",
                "author_association": "MEMBER",
                "user": {"login": "verifier"},
            }
        ]

    def pull_request_files(self, number: int) -> tuple[str, ...]:
        return ("tools/governance.py",)

    def pull_request_commits(self, number: int) -> list[dict[str, object]]:
        return [{"committer": {"login": "owner"}}]

    def pull_request_reviews(self, number: int) -> list[dict[str, object]]:
        return []


def test_rework_immediately_invalidates_green_governance_status() -> None:
    client = FakeTransitionClient()
    event = {
        "issue": {"number": 9},
        "comment": {"body": "/transition REWORK", "author_association": "OWNER"},
    }

    assert handle_transition(event, client) == 0
    assert client.statuses == [("a" * 40, "pending", "任务状态为 REWORK")]


def test_l0_rejects_governance_security_architecture_runtime_and_workflow_files() -> None:
    protected = (
        "AGENTS.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        ".github/workflows/ci.yml",
        "docs/architecture.md",
        "docs/safety-model.md",
        "docs/governance/RELEASE_POLICY.md",
        "docs/adr/ADR-1.md",
        "docs/codex/CURRENT_TASK.md",
    )

    assert all(not _is_small_documentation_change((path,)) for path in protected)


def test_l0_allows_only_low_risk_documentation_paths() -> None:
    assert _is_small_documentation_change(("README.md",))
    assert _is_small_documentation_change(("docs/typo.md",))
    assert not _is_small_documentation_change(("src/quant_lab/gates.py",))


def test_paginated_pull_request_files_cannot_hide_non_documentation_change() -> None:
    class PagedClient(GitHubClient):
        def __init__(self) -> None:
            super().__init__("owner/repo", "token")

        def request(self, method: str, path: str, payload: dict[str, object] | None = None):
            if path.endswith("page=1"):
                return [{"filename": "docs/typo.md"} for _ in range(100)]
            if path.endswith("page=2"):
                return [{"filename": "src/quant_lab/gates.py"}]
            raise AssertionError(path)

    files = PagedClient().pull_request_files(10)

    assert len(files) == 101
    assert not _is_small_documentation_change(files)


def test_acceptance_refuses_invalid_current_pull_request() -> None:
    client = FakeTransitionClient()
    client.pull_body = "Closes #9\n## 变更\n缺少其余章节"
    event = {
        "issue": {"number": 9},
        "comment": {"body": "/transition ACCEPTED", "author_association": "OWNER"},
    }

    assert handle_transition(event, client) == 1
    assert client.statuses == [("a" * 40, "failure", "治理检查失败")]


def test_code_task_manual_closed_transition_is_rejected() -> None:
    class AcceptedClient(FakeTransitionClient):
        def issue(self, number: int) -> dict[str, object]:
            issue = super().issue(number)
            issue["labels"] = [{"name": "status:accepted"}]
            return issue

    client = AcceptedClient()
    event = {
        "issue": {"number": 9},
        "comment": {"body": "/transition CLOSED", "author_association": "OWNER"},
    }

    assert handle_transition(event, client) == 1
    assert client.statuses == [("a" * 40, "failure", "治理检查失败")]


def test_review_verification_requires_trusted_independent_reviewer() -> None:
    class ReviewClient:
        def issue_comments(self, number: int) -> list[dict[str, object]]:
            return []

        def pull_request_reviews(self, number: int) -> list[dict[str, object]]:
            return [
                {
                    "state": "APPROVED",
                    "commit_id": "a" * 40,
                    "user": {"login": "external"},
                    "author_association": "NONE",
                }
            ]

        def pull_request_commits(self, number: int) -> list[dict[str, object]]:
            return [{"author": {"login": "implementer"}, "committer": {"login": "implementer"}}]

    pull = {"head": {"sha": "a" * 40}, "user": {"login": "implementer"}, "number": 10}

    assert not _verification_passed(ReviewClient(), 9, pull)


def test_bot_verification_cannot_count_as_independent() -> None:
    class BotClient:
        def issue_comments(self, number: int) -> list[dict[str, object]]:
            return [
                {
                    "body": f"/verify PASS {'a' * 40}",
                    "author_association": "MEMBER",
                    "user": {"login": "review-bot[bot]", "type": "Bot"},
                }
            ]

        def pull_request_reviews(self, number: int) -> list[dict[str, object]]:
            return []

        def pull_request_commits(self, number: int) -> list[dict[str, object]]:
            return [{"committer": {"login": "implementer"}}]

    pull = {"head": {"sha": "a" * 40}, "user": {"login": "implementer"}, "number": 10}

    assert not _verification_passed(BotClient(), 9, pull)


def test_review_verification_rejects_last_pusher_and_review_state_retraction() -> None:
    class ReviewClient:
        def issue_comments(self, number: int) -> list[dict[str, object]]:
            return []

        def pull_request_reviews(self, number: int) -> list[dict[str, object]]:
            return [
                {
                    "state": "APPROVED",
                    "commit_id": "a" * 40,
                    "user": {"login": "reviewer"},
                    "author_association": "MEMBER",
                },
                {
                    "state": "CHANGES_REQUESTED",
                    "commit_id": "a" * 40,
                    "user": {"login": "reviewer"},
                    "author_association": "MEMBER",
                },
            ]

        def pull_request_commits(self, number: int) -> list[dict[str, object]]:
            return [{"author": {"login": "reviewer"}, "committer": {"login": "reviewer"}}]

    pull = {"head": {"sha": "a" * 40}, "user": {"login": "implementer"}, "number": 10}

    assert not _verification_passed(ReviewClient(), 9, pull)


def test_issue_comment_deletion_recomputes_governance() -> None:
    client = FakeVerificationClient()
    client.statuses = []
    event = {"action": "deleted", "issue": {"number": 9}, "comment": {}}

    assert handle_verification(event, client) == 0
    assert client.statuses == [("a" * 40, "pending", "等待独立验收通过")]


def test_revoked_current_acceptance_returns_to_verification() -> None:
    client = FakePullRequestClient("ACCEPTED")
    event = {"action": "dismissed", "pull_request": PR_EVENT["pull_request"]}

    assert handle_pull_request(event, client) == 0
    assert client.statuses == [
        ("a" * 40, "pending", "等待当前提交的独立验收")
    ]


def test_closed_issue_label_cannot_skip_merge_gate() -> None:
    client = FakeTransitionClient()
    event = {"issue": {"number": 9}}

    assert handle_issue_closed(event, client) == 1


class FakeClosedPullRequestClient:
    def __init__(
        self,
        *,
        issue_status: str = "ACCEPTED",
        verification_sha: str | None = "a" * 40,
        current_head: str = "a" * 40,
        merged: bool = True,
        merge_commit_sha: str | None = "c" * 40,
        other_open: bool = False,
    ) -> None:
        self.issue_status = issue_status
        self.verification_sha = verification_sha
        self.current_head = current_head
        self.merged = merged
        self.merge_commit_sha = merge_commit_sha
        self.other_open = other_open
        self.updates: list[dict[str, object]] = []
        self.comments: list[str] = []

    def issue(self, number: int) -> dict[str, object]:
        assert number == 9
        return {
            "number": 9,
            "body": READY_BODY,
            "labels": [{"name": f"status:{self.issue_status.lower().replace('_', '-')}"}],
            "assignees": [{"login": "owner"}],
        }

    def pull_requests(self) -> list[dict[str, object]]:
        pulls = [
            {
                "number": 10,
                "state": "closed",
                "body": PR_EVENT["pull_request"]["body"],
                "head": {"sha": self.current_head},
                "user": {"login": "implementer"},
                "merged": self.merged,
                "merged_at": "2026-09-17T05:00:00Z" if self.merged else None,
                "merge_commit_sha": self.merge_commit_sha,
            }
        ]
        if self.other_open:
            pulls.append(
                {
                    "number": 11,
                    "state": "open",
                    "body": PR_EVENT["pull_request"]["body"],
                    "head": {"sha": "b" * 40},
                    "user": {"login": "implementer"},
                }
            )
        return pulls

    def issue_comments(self, number: int) -> list[dict[str, object]]:
        if self.verification_sha is None:
            return []
        return [
            {
                "body": f"/verify PASS {self.verification_sha}",
                "author_association": "MEMBER",
                "user": {"login": "verifier"},
            }
        ]

    def pull_request_reviews(self, number: int) -> list[dict[str, object]]:
        return []

    def pull_request_commits(self, number: int) -> list[dict[str, object]]:
        return [{"committer": {"login": "implementer"}}]

    def update_issue(self, number: int, **changes: object) -> None:
        assert number == 9
        self.updates.append(changes)

    def comment(self, number: int, body: str) -> None:
        assert number == 9
        self.comments.append(body)


def _closed_pull_request_event(
    client: FakeClosedPullRequestClient,
) -> dict[str, object]:
    return {
        "action": "closed",
        "pull_request": {
            **PR_EVENT["pull_request"],
            "number": 10,
            "head": {"sha": client.current_head},
            "merged": client.merged,
            "merge_commit_sha": client.merge_commit_sha,
        },
    }


def _closed_pull_request_audit(
    number: int, head_sha: str, merge_commit_sha: str
) -> str:
    return (
        "<!-- governance-audit: closed-by-pr PR "
        f"{number} HEAD {head_sha} MERGE {merge_commit_sha} -->"
    )


def test_exact_merged_pull_request_close_event_closes_accepted_issue() -> None:
    client = FakeClosedPullRequestClient()

    assert handle_pull_request(_closed_pull_request_event(client), client) == 0
    assert client.updates == [
        {"labels": ["status:closed"], "state": "closed"}
    ]
    assert client.comments == [
        "<!-- governance-audit: closed-by-pr PR 10 HEAD "
        + "a" * 40
        + " MERGE "
        + "c" * 40
        + " -->"
    ]


def test_issue_closed_accepts_only_pull_request_close_audit() -> None:
    class AuthorizedCloseClient(FakeClosedPullRequestClient):
        def issue(self, number: int) -> dict[str, object]:
            issue = super().issue(number)
            issue["labels"] = [{"name": "status:closed"}]
            return issue

        def issue_comments(self, number: int) -> list[dict[str, object]]:
            return [
                {
                    "body": _closed_pull_request_audit(10, "a" * 40, "c" * 40),
                    "user": {"login": "github-actions[bot]"},
                }
            ]

    client = AuthorizedCloseClient()

    assert handle_issue_closed({"issue": {"number": 9}}, client) == 0
    assert client.updates == []


def test_issue_closed_rejects_unbound_or_expired_pull_request_audits() -> None:
    class CloseAuditClient(FakeClosedPullRequestClient):
        def __init__(
            self,
            audit: str,
            *,
            current_head: str = "a" * 40,
            merge_commit_sha: str | None = "c" * 40,
        ) -> None:
            super().__init__(
                current_head=current_head,
                merge_commit_sha=merge_commit_sha,
            )
            self.audit = audit

        def issue(self, number: int) -> dict[str, object]:
            issue = super().issue(number)
            issue["labels"] = [{"name": "status:closed"}]
            return issue

        def issue_comments(self, number: int) -> list[dict[str, object]]:
            return [
                {
                    "body": self.audit,
                    "user": {"login": "github-actions[bot]"},
                }
            ]

    cases = (
        (
            "wrong PR",
            _closed_pull_request_audit(123, "a" * 40, "c" * 40),
            "a" * 40,
            "c" * 40,
        ),
        (
            "wrong HEAD",
            _closed_pull_request_audit(10, "b" * 40, "c" * 40),
            "a" * 40,
            "c" * 40,
        ),
        (
            "wrong merge SHA",
            _closed_pull_request_audit(10, "a" * 40, "d" * 40),
            "a" * 40,
            "c" * 40,
        ),
        (
            "forged merge text",
            _closed_pull_request_audit(123, "b" * 40, "forged"),
            "a" * 40,
            "c" * 40,
        ),
        (
            "expired audit",
            _closed_pull_request_audit(10, "a" * 40, "c" * 40),
            "b" * 40,
            "d" * 40,
        ),
    )

    for name, audit, current_head, merge_commit_sha in cases:
        client = CloseAuditClient(
            audit,
            current_head=current_head,
            merge_commit_sha=merge_commit_sha,
        )

        assert handle_issue_closed({"issue": {"number": 9}}, client) == 1, name
        assert client.updates == [{"state": "open"}], name


def test_old_merged_pull_request_cannot_close_issue_with_new_open_pull_request() -> None:
    client = FakeClosedPullRequestClient(other_open=True)

    assert handle_pull_request(_closed_pull_request_event(client), client) == 1
    assert client.updates == []


def test_closed_pull_request_close_gate_rejects_invalid_events() -> None:
    cases = (
        {"current_head": "b" * 40},
        {"verification_sha": None},
        {"merge_commit_sha": None},
        {"other_open": True},
        {"issue_status": "READY_FOR_VERIFY"},
    )

    for options in cases:
        client = FakeClosedPullRequestClient(**options)
        assert handle_pull_request(_closed_pull_request_event(client), client) == 1
        assert client.updates == []


def test_unmerged_closed_pull_request_does_not_change_issue() -> None:
    client = FakeClosedPullRequestClient(merged=False)

    assert handle_pull_request(_closed_pull_request_event(client), client) == 0
    assert client.updates == []


def test_historical_merged_pull_request_cannot_authorize_issue_close() -> None:
    class MergedReworkCloseClient(FakeTransitionClient):
        def __init__(self) -> None:
            super().__init__()
            self.updates: list[dict[str, object]] = []
            self.comments: list[str] = []

        def issue(self, number: int) -> dict[str, object]:
            assert number == 9
            return {
                "number": 9,
                "body": READY_BODY,
                "labels": [{"name": "status:rework"}],
                "assignees": [{"login": "owner"}],
            }

        def pull_requests(self) -> list[dict[str, object]]:
            return [
                {
                    "number": 10,
                    "state": "closed",
                    "body": self.pull_body,
                    "head": {"sha": "a" * 40},
                    "user": {"login": "owner"},
                    "merged_at": "2026-09-17T05:00:00Z",
                }
            ]

        def update_issue(self, number: int, **changes: object) -> None:
            assert number == 9
            self.updates.append(changes)

        def comment(self, number: int, body: str) -> None:
            assert number == 9
            self.comments.append(body)

    client = MergedReworkCloseClient()

    assert handle_issue_closed({"issue": {"number": 9}}, client) == 1
    assert client.updates == [{"state": "open"}]


def test_analysis_issue_can_close_with_a_close_conclusion() -> None:
    context = TransitionContext(
        body="## 关闭结论\n已完成分析。",
        labels=frozenset({"type:analysis"}),
    )

    assert validate_transition("ANALYZING", "CLOSED", context) == []


def test_manual_status_label_change_fails_closed() -> None:
    client = FakeTransitionClient()
    event = {
        "action": "labeled",
        "issue": {"number": 9},
        "label": {"name": "status:accepted"},
        "sender": {"login": "owner"},
    }

    assert handle_issue_label_change(event, client) == 1
    assert client.statuses == [("a" * 40, "failure", "治理检查失败")]


def test_verification_record_cannot_clear_manual_label_failure_audit() -> None:
    class AuditClient:
        def __init__(self, comments: list[dict[str, object]]) -> None:
            self.comments = comments

        def issue_comments(self, number: int) -> list[dict[str, object]]:
            return self.comments

    bot = {"login": "github-actions[bot]"}
    invalid = {"body": "<!-- governance-audit: invalid-status-label-change -->", "user": bot}
    verification = {"body": "<!-- governance-audit: verification aaaa -->", "user": bot}
    state = {"body": "<!-- governance-audit: state READY_FOR_VERIFY -->", "user": bot}

    assert _manual_label_change_detected(AuditClient([invalid, verification]), 9)
    assert not _manual_label_change_detected(AuditClient([invalid, state]), 9)


def test_accepted_state_can_return_to_verification() -> None:
    context = TransitionContext(body=READY_BODY, open_pull_request=True)

    assert validate_transition("ACCEPTED", "READY_FOR_VERIFY", context) == []


def test_bootstrap_workflow_never_uses_pr_checker_when_base_has_none() -> None:
    workflow = Path(".github/workflows/governance.yml").read_text(encoding="utf-8")

    assert "cp tools/governance.py" not in workflow
    assert "Bootstrap: base has no trusted checker; fail closed." in workflow
    assert "exit 1" in workflow
    assert "types: [created, edited, deleted]" in workflow
    assert "types: [submitted, edited, dismissed]" in workflow
    assert "issues: write" in workflow
    assert (
        "types: [opened, edited, synchronize, reopened, ready_for_review, "
        "converted_to_draft, closed]"
    ) in workflow
    assert "startsWith(github.event.comment.body, '/verify ')" in workflow
    assert "startsWith(github.event.comment.body, '/verify PASS ')" not in workflow
    assert workflow.count("record-verification:") == 1
    assert "record-solo-verification:" not in workflow
