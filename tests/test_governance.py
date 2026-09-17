from tools.governance import (
    PullRequestContext,
    TransitionContext,
    extract_linked_issue,
    handle_pull_request,
    handle_transition,
    handle_verification,
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

    assert errors == ["CLOSED 缺少已合并 Pull Request"]


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
        return {"labels": [{"name": label}]}

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


class FakeVerificationClient:
    def __init__(self) -> None:
        self.comments: list[str] = []

    def issue(self, number: int) -> dict[str, object]:
        assert number == 9
        return {"labels": [{"name": "status:ready-for-verify"}]}

    def pull_requests(self) -> list[dict[str, object]]:
        return [
            {
                "number": 10,
                "state": "open",
                "body": "Closes #9",
                "head": {"sha": "a" * 40},
                "user": {"login": "implementer"},
            }
        ]

    def comment(self, number: int, body: str) -> None:
        assert number == 9
        self.comments.append(body)


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
    assert client.comments == ["治理门禁拒绝：实施者不能验收自己的 Pull Request。"]


class FakeTransitionClient:
    def __init__(self) -> None:
        self.statuses: list[tuple[str, str, str]] = []

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
                "body": "Closes #9",
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


def test_rework_immediately_invalidates_green_governance_status() -> None:
    client = FakeTransitionClient()
    event = {
        "issue": {"number": 9},
        "comment": {"body": "/transition REWORK", "author_association": "OWNER"},
    }

    assert handle_transition(event, client) == 0
    assert client.statuses == [("a" * 40, "pending", "任务状态为 REWORK")]
