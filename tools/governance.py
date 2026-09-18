from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STATE_PREFIX = "status:"
TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
BOT_LOGIN = "github-actions[bot]"
AUDIT_PREFIX = "<!-- governance-audit:"
HIGH_RISK_PREFIXES = (
    ".github/",
    "config/",
    "tools/",
    "docs/adr/",
    "docs/codex/",
    "docs/governance/",
    "docs/operations/",
    "docs/runtime/",
)
HIGH_RISK_FILES = frozenset(
    {
        "AGENTS.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "pyproject.toml",
        "src/quant_lab/dry_run.py",
        "src/quant_lab/gates.py",
        "src/quant_lab/release.py",
        "src/quant_lab/validation.py",
        "tests/test_dry_run_supervisor.py",
        "tests/test_gates.py",
        "tests/test_governance.py",
        "tests/test_release.py",
        "tests/test_validation.py",
    }
)
# Keep this empty until a real ordinary module is reviewed and listed explicitly.
EXPLICIT_L1_FILES = frozenset()
ISSUE_CONTRACT_SECTIONS = ("目标", "范围", "不在范围", "验收标准", "风险与回滚")
PR_SECTIONS = ("变更", "证据", "风险与回滚", "未验证事项", "独立验收")
CLOSED_PR_AUDIT_RE = re.compile(
    r"^<!-- governance-audit: closed-by-pr PR (?P<number>[1-9][0-9]*) "
    r"HEAD (?P<head>[0-9a-fA-F]{40}) "
    r"MERGE (?P<merge>[0-9a-fA-F]{40}) -->$"
)

TRANSITIONS = {
    "": {"DRAFT"},
    "DRAFT": {"ANALYZING", "BLOCKED"},
    "ANALYZING": {"READY", "BLOCKED"},
    "READY": {"IN_PROGRESS", "BLOCKED"},
    "IN_PROGRESS": {"READY_FOR_VERIFY", "BLOCKED"},
    "READY_FOR_VERIFY": {"ACCEPTED", "REWORK", "BLOCKED"},
    "REWORK": {"IN_PROGRESS", "BLOCKED"},
    "BLOCKED": {"ANALYZING"},
    "ACCEPTED": {"READY_FOR_VERIFY", "CLOSED"},
    "CLOSED": set(),
}
VALID_STATES = frozenset(TRANSITIONS)


@dataclass(frozen=True)
class TransitionContext:
    body: str
    labels: frozenset[str] = frozenset()
    assignees: tuple[str, ...] = ()
    branch_exists: bool = False
    open_pull_request: bool = False
    independent_verification_passed: bool = False
    risk_class: str | None = None


@dataclass(frozen=True)
class PullRequestContext:
    body: str
    draft: bool
    changed_files: tuple[str, ...]
    linked_issue_number: int | None = None
    linked_issue_status: str | None = None


def _audit_marker(kind: str, value: str = "") -> str:
    suffix = f" {value}" if value else ""
    return f"{AUDIT_PREFIX} {kind}{suffix} -->"


def markdown_sections(body: str) -> set[str]:
    return {
        match.group(1).strip()
        for match in re.finditer(r"^#{2,4}\s+(.+?)\s*$", body, flags=re.MULTILINE)
    }


def missing_sections(body: str, required: tuple[str, ...]) -> list[str]:
    sections = markdown_sections(body)
    return [section for section in required if section not in sections]


def parse_transition_command(text: str) -> str | None:
    match = re.fullmatch(r"\s*/transition\s+([A-Za-z_]+)\s*", text)
    if not match:
        return None
    state = match.group(1).upper()
    return state if state in VALID_STATES else None


def parse_verification_command(text: str) -> str | None:
    match = re.fullmatch(r"\s*/verify\s+PASS\s+([0-9a-fA-F]{40})\s*", text)
    return match.group(1).lower() if match else None


def parse_solo_verification_command(text: str) -> tuple[str, str] | None:
    match = re.fullmatch(
        r"\s*/verify\s+SOLO\s+PASS\s+([0-9a-fA-F]{40})\s+EVIDENCE\s+"
        r"((?:https?://|codex://)\S+)\s*",
        text,
    )
    return (match.group(1).lower(), match.group(2)) if match else None


def _valid_repo_relative_path(path: str) -> bool:
    if not path or path.startswith("/") or "\\" in path:
        return False
    parts = path.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


def _valid_evidence_reference(reference: str, repository: str, pull_number: int) -> bool:
    parts = urllib.parse.urlsplit(reference)
    if parts.scheme == "https":
        if parts.netloc != "github.com" or parts.fragment:
            return False
        path = urllib.parse.unquote(parts.path)
        prefix = f"/{repository}/"
        if not path.startswith(prefix):
            return False
        relative = path[len(prefix) :]
        segments = relative.split("/")
        if any(segment in {"", ".", ".."} for segment in segments):
            return False
        if segments[0] in {"issues", "pull"}:
            return len(segments) == 2 and segments[1].isdigit() and int(segments[1]) > 0
        if segments[0] == "commit":
            return bool(
                len(segments) == 2
                and re.fullmatch(r"[0-9a-fA-F]{7,64}", segments[1])
            )
        if segments[0] == "blob":
            return len(segments) >= 3 and _valid_repo_relative_path("/".join(segments[2:]))
        return False
    if parts.scheme != "codex" or parts.netloc != "review" or parts.path or parts.fragment:
        return False
    query = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
    if set(query) != {"pr", "path", "line", "side"} or any(
        len(values) != 1 for values in query.values()
    ):
        return False
    expected_pr = f"https://github.com/{repository}/pull/{pull_number}"
    return (
        query["pr"][0] == expected_pr
        and _valid_repo_relative_path(query["path"][0])
        and bool(re.fullmatch(r"[1-9][0-9]*", query["line"][0]))
        and query["side"][0] in {"left", "right"}
    )


def status_from_labels(labels: tuple[str, ...] | list[str]) -> str:
    states = [
        label.removeprefix(STATE_PREFIX).replace("-", "_").upper()
        for label in labels
        if label.startswith(STATE_PREFIX)
    ]
    if len(states) > 1:
        raise ValueError("Issue 同时存在多个状态标签")
    return states[0] if states else ""


def extract_linked_issue(body: str) -> int | None:
    match = re.search(
        r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b",
        body,
        flags=re.IGNORECASE,
    )
    return int(match.group(1)) if match else None


def validate_transition(
    current_state: str | None, target_state: str, context: TransitionContext
) -> list[str]:
    current = (current_state or "").upper()
    target = target_state.upper()
    analysis_close = (
        target == "CLOSED"
        and "type:analysis" in context.labels
        and "关闭结论" in markdown_sections(context.body)
    )
    compact_path = (
        target == "IN_PROGRESS"
        and current in {"DRAFT", "ANALYZING"}
        and context.risk_class == "L1"
    )
    if target not in TRANSITIONS.get(current, set()) and not compact_path and not analysis_close:
        return [f"非法状态流转：{current or 'NONE'} -> {target}"]

    errors: list[str] = []
    if target == "READY":
        missing = missing_sections(context.body, ISSUE_CONTRACT_SECTIONS)
        if missing:
            errors.append(f"READY 缺少章节：{'、'.join(missing)}")
    elif target == "IN_PROGRESS":
        if not context.assignees:
            errors.append("IN_PROGRESS 缺少责任人")
        if not context.branch_exists:
            errors.append("IN_PROGRESS 缺少任务分支")
        if compact_path and not context.open_pull_request:
            errors.append("紧凑路径缺少关联 Pull Request")
    elif target == "READY_FOR_VERIFY" and not context.open_pull_request:
        errors.append("READY_FOR_VERIFY 缺少关联 Pull Request")
    elif target == "ACCEPTED" and not context.independent_verification_passed:
        errors.append("ACCEPTED 缺少独立验收通过记录")
    elif target == "CLOSED" and not analysis_close:
        errors.append("代码任务必须由准确的 Pull Request closed 事件关闭")
    return errors


def validate_pull_request(context: PullRequestContext) -> list[str]:
    l0_exception = bool(re.search(r"-\s*\[x\]\s*L0\s*例外", context.body, re.IGNORECASE))
    if context.linked_issue_number is None:
        if not l0_exception:
            return ["Pull Request 缺少关联 Issue"]
        if not _is_small_documentation_change(context.changed_files):
            return ["L0 例外包含非小型文档变更"]
        return []

    errors: list[str] = []
    missing = missing_sections(context.body, PR_SECTIONS)
    if missing:
        errors.append(f"Pull Request 缺少章节：{'、'.join(missing)}")

    status = (context.linked_issue_status or "").upper()
    risk_class = classify_change_files(context.changed_files)
    if context.draft and risk_class == "L1":
        allowed = {"DRAFT", "ANALYZING", "READY", "IN_PROGRESS", "READY_FOR_VERIFY", "ACCEPTED"}
    elif context.draft:
        allowed = {"IN_PROGRESS", "READY_FOR_VERIFY", "ACCEPTED"}
    else:
        allowed = {"READY_FOR_VERIFY", "ACCEPTED"}
    if status not in allowed:
        kind = "Draft" if context.draft else "非 Draft"
        expected = "DRAFT、ANALYZING、READY、IN_PROGRESS、READY_FOR_VERIFY 或 ACCEPTED" if (
            context.draft and risk_class == "L1"
        ) else "IN_PROGRESS、READY_FOR_VERIFY 或 ACCEPTED" if context.draft else (
            "READY_FOR_VERIFY 或 ACCEPTED"
        )
        errors.append(f"{kind} Pull Request 要求关联 Issue 为 {expected}")
    return errors


def _is_small_documentation_change(files: tuple[str, ...]) -> bool:
    protected_prefixes = (
        ".github/",
        "docs/governance/",
        "docs/adr/",
        "docs/codex/",
        "docs/runtime/",
        "docs/operations/",
    )
    protected_files = {
        "AGENTS.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "docs/architecture.md",
        "docs/safety-model.md",
    }
    return bool(files) and all(
        path.endswith(".md")
        and (path.startswith("docs/") or path in {"README.md", "CHANGELOG.md"})
        and not path.startswith(protected_prefixes)
        and path not in protected_files
        for path in files
    )


def classify_change_files(files: tuple[str, ...]) -> str:
    """Classify only explicit low-risk paths; everything else fails closed."""
    if not files:
        return "HIGH"
    if _is_small_documentation_change(files):
        return "L0"
    normalized = tuple(path.replace("\\", "/") for path in files)
    if any(path in HIGH_RISK_FILES or path.startswith(HIGH_RISK_PREFIXES) for path in normalized):
        return "HIGH"
    if all(path in EXPLICIT_L1_FILES for path in normalized):
        return "L1"
    return "HIGH"


class GitHubClient:
    def __init__(self, repository: str, token: str) -> None:
        self.repository = repository
        self.token = token
        self.api_root = f"https://api.github.com/repos/{repository}"

    @property
    def repository_owner(self) -> str:
        return self.repository.split("/", 1)[0]

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self.api_root}{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"GitHub API {method} {path} failed: {exc.code} {detail}") from exc
        return json.loads(content) if content else None

    def issue(self, number: int) -> dict[str, Any]:
        return self.request("GET", f"/issues/{number}")

    def branches(self) -> list[dict[str, Any]]:
        return self.request("GET", "/branches?per_page=100")

    def pull_requests(self) -> list[dict[str, Any]]:
        return self.request("GET", "/pulls?state=all&per_page=100")

    def pull_request_files(self, number: int) -> tuple[str, ...]:
        files: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self.request("GET", f"/pulls/{number}/files?per_page=100&page={page}")
            files.extend(batch)
            if len(batch) < 100:
                return tuple(item["filename"] for item in files)
            page += 1

    def pull_request_commits(self, number: int) -> list[dict[str, Any]]:
        commits: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self.request("GET", f"/pulls/{number}/commits?per_page=100&page={page}")
            commits.extend(batch)
            if len(batch) < 100:
                return commits
            page += 1

    def pull_request_reviews(self, number: int) -> list[dict[str, Any]]:
        return self.request("GET", f"/pulls/{number}/reviews?per_page=100")

    def issue_comments(self, number: int) -> list[dict[str, Any]]:
        return self.request("GET", f"/issues/{number}/comments?per_page=100")

    def update_issue(self, number: int, **changes: Any) -> None:
        self.request("PATCH", f"/issues/{number}", changes)

    def comment(self, number: int, body: str) -> None:
        self.request("POST", f"/issues/{number}/comments", {"body": body})

    def set_commit_status(self, sha: str, state: str, description: str) -> None:
        self.request(
            "POST",
            f"/statuses/{sha}",
            {"state": state, "context": "governance", "description": description},
        )


def _label_names(issue: dict[str, Any]) -> tuple[str, ...]:
    return tuple(label["name"] for label in issue.get("labels", []))


def _status_label(state: str) -> str:
    return f"{STATE_PREFIX}{state.lower().replace('_', '-')}"


def _related_pull_requests(client: GitHubClient, issue_number: int) -> list[dict[str, Any]]:
    return [
        pull
        for pull in client.pull_requests()
        if extract_linked_issue(pull.get("body") or "") == issue_number
    ]


def _branch_exists(client: GitHubClient, issue_number: int) -> bool:
    prefixes = tuple(
        f"{kind}/{issue_number}-" for kind in ("codex", "feature", "fix", "docs", "chore")
    )
    return any(branch["name"].startswith(prefixes) for branch in client.branches())


def _verification_passed(
    client: GitHubClient, issue_number: int, pull: dict[str, Any]
) -> bool:
    head_sha = (pull.get("head", {}).get("sha") or "").lower()
    author = (pull.get("user") or {}).get("login")
    last_pusher = _last_pusher_login(client, pull)
    repository_owner = _repository_owner(client)
    solo_comment_passed = any(
        (record := parse_solo_verification_command(comment.get("body") or ""))
        and record[0] == head_sha
        and _valid_evidence_reference(record[1], _repository_name(client), pull["number"])
        and comment.get("author_association") in TRUSTED_ASSOCIATIONS
        and (comment.get("user") or {}).get("login") == repository_owner
        and not _is_bot_user(comment.get("user") or {})
        for comment in client.issue_comments(issue_number)
    )
    comment_passed = any(
        comment.get("author_association") in TRUSTED_ASSOCIATIONS
        and (comment.get("user") or {}).get("login")
        and not _is_bot_user(comment.get("user") or {})
        and (comment.get("user") or {}).get("login") not in {author, last_pusher}
        and parse_verification_command(comment.get("body") or "") == head_sha
        for comment in client.issue_comments(issue_number)
    )
    latest_reviews: dict[str, dict[str, Any]] = {}
    for review in client.pull_request_reviews(pull["number"]):
        login = (review.get("user") or {}).get("login")
        if login:
            latest_reviews[login] = review
    review_passed = any(
        review.get("state") == "APPROVED"
        and review.get("author_association") in TRUSTED_ASSOCIATIONS
        and not _is_bot_user(review.get("user") or {})
        and login not in {author, last_pusher}
        and (review.get("commit_id") or "").lower() == head_sha
        for login, review in latest_reviews.items()
    )
    return solo_comment_passed or comment_passed or review_passed


def _last_pusher_login(client: GitHubClient, pull: dict[str, Any]) -> str | None:
    get_commits = getattr(client, "pull_request_commits", None)
    if get_commits is None:
        return None
    commits = get_commits(pull["number"])
    if not commits:
        return None
    last = commits[-1]
    return (
        (last.get("committer") or {}).get("login")
        or (last.get("author") or {}).get("login")
    )


def _repository_owner(client: GitHubClient) -> str:
    owner = getattr(client, "repository_owner", "")
    if owner:
        return owner
    return _repository_name(client).split("/", 1)[0]


def _repository_name(client: GitHubClient) -> str:
    return getattr(client, "repository", "")


def _is_bot_user(user: dict[str, Any]) -> bool:
    login = user.get("login") or ""
    return user.get("type") == "Bot" or login.endswith("[bot]")


def _manual_label_change_detected(client: GitHubClient, issue_number: int) -> bool:
    for comment in reversed(client.issue_comments(issue_number)):
        body = comment.get("body") or ""
        if not body.startswith(AUDIT_PREFIX):
            continue
        if (comment.get("user") or {}).get("login") != BOT_LOGIN:
            continue
        if "invalid-status-label-change" in body:
            return True
        if " state " in body:
            return False
    return False


def _pull_request_errors(
    client: GitHubClient, issue: dict[str, Any], pull: dict[str, Any]
) -> list[str]:
    issue_number = issue["number"]
    return validate_pull_request(
        PullRequestContext(
            body=pull.get("body") or "",
            draft=bool(pull.get("draft")),
            changed_files=client.pull_request_files(pull["number"]),
            linked_issue_number=issue_number,
            linked_issue_status=status_from_labels(_label_names(issue)),
        )
    )


def _transition_context(
    client: GitHubClient, issue: dict[str, Any], target_state: str
) -> TransitionContext:
    issue_number = issue["number"]
    pulls = _related_pull_requests(client, issue_number)
    open_pulls = [pull for pull in pulls if pull["state"] == "open"]
    risk_class = None
    if len(open_pulls) == 1:
        risk_class = classify_change_files(client.pull_request_files(open_pulls[0]["number"]))
    verification_passed = bool(
        target_state == "ACCEPTED"
        and len(open_pulls) == 1
        and _verification_passed(client, issue_number, open_pulls[0])
    )
    return TransitionContext(
        body=issue.get("body") or "",
        labels=frozenset(_label_names(issue)),
        assignees=tuple(user["login"] for user in issue.get("assignees", [])),
        branch_exists=(
            _branch_exists(client, issue_number) if target_state == "IN_PROGRESS" else False
        ),
        open_pull_request=bool(open_pulls),
        independent_verification_passed=verification_passed,
        risk_class=risk_class,
    )


def _replace_status_label(issue: dict[str, Any], target_state: str) -> list[str]:
    labels = [
        label
        for label in _label_names(issue)
        if not label.startswith(STATE_PREFIX)
        and (target_state == "ACCEPTED" or label != "verification:passed")
    ]
    labels.append(_status_label(target_state))
    return labels


def _set_related_statuses(
    client: GitHubClient, issue_number: int, state: str, description: str
) -> None:
    for pull in _related_pull_requests(client, issue_number):
        if pull["state"] == "open":
            client.set_commit_status(pull["head"]["sha"], state, description)


def _closed_pull_request_audit(pull: dict[str, Any]) -> str:
    return _audit_marker(
        "closed-by-pr",
        f"PR {pull['number']} HEAD {pull['head']['sha']} MERGE {pull['merge_commit_sha']}",
    )


def _has_authorized_pull_request_close(
    client: GitHubClient, issue_number: int
) -> bool:
    related_pulls = {
        pull.get("number"): pull for pull in _related_pull_requests(client, issue_number)
    }
    for comment in client.issue_comments(issue_number):
        if (comment.get("user") or {}).get("login") != BOT_LOGIN:
            continue
        match = CLOSED_PR_AUDIT_RE.fullmatch(comment.get("body") or "")
        if match is None:
            continue
        pull = related_pulls.get(int(match["number"]))
        if pull is None or pull.get("state") != "closed":
            continue
        if (pull.get("head") or {}).get("sha", "").lower() != match["head"].lower():
            continue
        if (pull.get("merge_commit_sha") or "").lower() != match["merge"].lower():
            continue
        if pull.get("merged") is not True and not pull.get("merged_at"):
            continue
        return True
    return False


def handle_issue_opened(event: dict[str, Any], client: GitHubClient) -> int:
    issue = event["issue"]
    if status_from_labels(_label_names(issue)):
        return 0
    client.update_issue(issue["number"], labels=_replace_status_label(issue, "DRAFT"))
    client.comment(issue["number"], _audit_marker("state", "DRAFT"))
    return 0


def handle_transition(event: dict[str, Any], client: GitHubClient) -> int:
    comment = event["comment"]
    target = parse_transition_command(comment.get("body") or "")
    if target is None:
        return 0
    if comment.get("author_association") not in TRUSTED_ASSOCIATIONS:
        client.comment(event["issue"]["number"], "治理门禁拒绝：只有仓库协作者可以改变状态。")
        return 1

    issue = client.issue(event["issue"]["number"])
    try:
        current = status_from_labels(_label_names(issue))
    except ValueError as exc:
        _set_related_statuses(client, issue["number"], "failure", "治理检查失败")
        client.comment(issue["number"], f"治理门禁拒绝：{exc}")
        return 1
    errors = validate_transition(current, target, _transition_context(client, issue, target))
    if errors:
        _set_related_statuses(client, issue["number"], "failure", "治理检查失败")
        client.comment(issue["number"], "治理门禁拒绝：\n- " + "\n- ".join(errors))
        return 1

    open_pulls = [
        pull
        for pull in _related_pull_requests(client, issue["number"])
        if pull["state"] == "open"
    ]
    if target == "ACCEPTED":
        if len(open_pulls) != 1:
            client.comment(issue["number"], "治理门禁拒绝：ACCEPTED 要求唯一开放 Pull Request。")
            return 1
        pr_errors = _pull_request_errors(client, issue, open_pulls[0])
        if pr_errors:
            client.set_commit_status(open_pulls[0]["head"]["sha"], "failure", "治理检查失败")
            client.comment(
                issue["number"],
                "治理门禁拒绝：当前 Pull Request 仍不合格。\n- "
                + "\n- ".join(pr_errors),
            )
            return 1

    changes: dict[str, Any] = {"labels": _replace_status_label(issue, target)}
    if target == "CLOSED":
        changes["state"] = "closed"
    client.update_issue(issue["number"], **changes)
    if target == "ACCEPTED":
        for pull in open_pulls:
            client.set_commit_status(pull["head"]["sha"], "success", "治理检查通过")
    elif target in {"IN_PROGRESS", "READY_FOR_VERIFY", "REWORK", "BLOCKED"}:
        for pull in open_pulls:
            client.set_commit_status(
                pull["head"]["sha"], "pending", f"任务状态为 {target}"
            )
    client.comment(
        issue["number"],
        f"治理门禁通过：`{current or 'NONE'}` → `{target}`。\n"
        f"{_audit_marker('state', target)}",
    )
    return 0


def handle_verification(event: dict[str, Any], client: GitHubClient) -> int:
    comment = event["comment"]
    solo_record = parse_solo_verification_command(comment.get("body") or "")
    verified_sha = solo_record[0] if solo_record else parse_verification_command(
        comment.get("body") or ""
    )
    if verified_sha is None:
        if event.get("action") in {"deleted", "edited"}:
            return _recompute_issue_governance(event["issue"]["number"], client)
        return 0
    issue_number = event["issue"]["number"]
    verifier = (comment.get("user") or {}).get("login")
    if comment.get("author_association") not in TRUSTED_ASSOCIATIONS or not verifier:
        client.comment(issue_number, "治理门禁拒绝：只有仓库协作者可以记录独立验收。")
        return 1

    issue = client.issue(issue_number)
    if status_from_labels(_label_names(issue)) != "READY_FOR_VERIFY":
        client.comment(issue_number, "治理门禁拒绝：只有 READY_FOR_VERIFY 可以记录验收。")
        return 1
    pulls = [
        pull for pull in _related_pull_requests(client, issue_number) if pull["state"] == "open"
    ]
    if len(pulls) != 1 or pulls[0]["head"]["sha"].lower() != verified_sha:
        client.comment(issue_number, "治理门禁拒绝：验收 SHA 与唯一开放 PR 的 HEAD 不一致。")
        return 1
    if solo_record and not _valid_evidence_reference(
        solo_record[1], _repository_name(client), pulls[0]["number"]
    ):
        client.comment(issue_number, "治理门禁拒绝：solo evidence 引用不可复核。")
        return 1
    if solo_record:
        repository_owner = _repository_owner(client)
        if comment.get("author_association") not in TRUSTED_ASSOCIATIONS:
            client.comment(
                issue_number,
                "治理门禁拒绝：solo owner attestation 需要可信仓库所有者身份。",
            )
            return 1
        if _is_bot_user(comment.get("user") or {}) or verifier != repository_owner:
            client.comment(
                issue_number,
                "治理门禁拒绝：solo owner attestation 必须由仓库所有者记录。",
            )
            return 1
    else:
        last_pusher = _last_pusher_login(client, pulls[0])
        if _is_bot_user(comment.get("user") or {}) or verifier in {
            (pulls[0].get("user") or {}).get("login"),
            last_pusher,
        }:
            client.comment(
                issue_number,
                "治理门禁拒绝：实施者或最后推送者不能独立验收 Pull Request。",
            )
            return 1
    pr_errors = _pull_request_errors(client, issue, pulls[0])
    if pr_errors:
        client.set_commit_status(pulls[0]["head"]["sha"], "failure", "治理检查失败")
        client.comment(
            issue_number,
            "治理门禁拒绝：当前 Pull Request 仍不合格。\n- " + "\n- ".join(pr_errors),
        )
        return 1

    labels = [label for label in _label_names(issue) if label != "verification:passed"]
    labels.append("verification:passed")
    client.update_issue(issue_number, labels=labels)
    if solo_record:
        client.comment(
            issue_number,
            f"已记录当前 PR HEAD `{verified_sha}` 的 solo owner attestation；"
            f"Codex 证据引用：`{solo_record[1]}`。",
        )
    else:
        client.comment(
            issue_number,
            f"已记录当前 PR HEAD `{verified_sha}` 的独立验收通过。\n"
            f"{_audit_marker('verification', verified_sha)}",
        )
    return 0


def handle_issue_closed(event: dict[str, Any], client: GitHubClient) -> int:
    issue = client.issue(event["issue"]["number"])
    current = status_from_labels(_label_names(issue))
    analysis_close = (
        "type:analysis" in _label_names(issue)
        and "关闭结论" in markdown_sections(issue.get("body") or "")
    )
    if analysis_close:
        return 0
    if current == "CLOSED" and _has_authorized_pull_request_close(client, issue["number"]):
        return 0
    client.update_issue(issue["number"], state="open")
    client.comment(
        issue["number"],
        "治理门禁重新打开 Issue：代码任务必须由准确的 Pull Request closed 事件关闭。",
    )
    return 1


def _recompute_pull_request_status(
    client: GitHubClient, issue: dict[str, Any], pull: dict[str, Any]
) -> int:
    issue_number = issue["number"]
    head_sha = pull["head"]["sha"]
    try:
        issue_status = status_from_labels(_label_names(issue))
        errors = _pull_request_errors(client, issue, pull)
    except (KeyError, ValueError) as exc:
        client.set_commit_status(head_sha, "failure", "治理检查失败")
        print(f"- 治理状态无法核对：{exc}", file=sys.stderr)
        return 1
    if errors or _manual_label_change_detected(client, issue_number):
        client.set_commit_status(head_sha, "failure", "治理检查失败")
        if errors:
            print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1

    has_verification_record = "verification:passed" in _label_names(issue)
    verification_current = (
        _verification_passed(client, issue_number, pull)
        if issue_status == "ACCEPTED" or has_verification_record
        else False
    )
    stale_acceptance = False
    if issue_status == "ACCEPTED" and not verification_current:
        stale_acceptance = True
        client.update_issue(issue_number, labels=_replace_status_label(issue, "READY_FOR_VERIFY"))
        client.comment(
            issue_number,
            "治理门禁失效当前验收：缺少当前 HEAD 的有效独立验收，已恢复 READY_FOR_VERIFY。\n"
            f"{_audit_marker('state', 'READY_FOR_VERIFY')}",
        )
        issue_status = "READY_FOR_VERIFY"
    elif "verification:passed" in _label_names(issue) and not verification_current:
        client.update_issue(issue_number, labels=_replace_status_label(issue, issue_status))
        client.comment(
            issue_number,
            "治理门禁失效当前验收：新提交未继承旧验收记录。\n"
            f"{_audit_marker('verification-invalidated', head_sha)}",
        )

    if issue_status == "ACCEPTED" and verification_current:
        client.set_commit_status(head_sha, "success", "治理检查通过")
        print("governance: PASS")
    else:
        description = "等待当前提交的独立验收" if stale_acceptance else "等待独立验收通过"
        client.set_commit_status(head_sha, "pending", description)
        print("governance: PENDING independent verification")
    return 0


def _recompute_issue_governance(issue_number: int, client: GitHubClient) -> int:
    issue = client.issue(issue_number)
    results = [
        _recompute_pull_request_status(client, issue, pull)
        for pull in _related_pull_requests(client, issue_number)
        if pull["state"] == "open"
    ]
    return 1 if any(result for result in results) else 0


def handle_issue_label_change(event: dict[str, Any], client: GitHubClient) -> int:
    label_name = (event.get("label") or {}).get("name") or ""
    if event.get("action") not in {"labeled", "unlabeled"} or not label_name.startswith(
        STATE_PREFIX
    ):
        return 0
    sender = event.get("sender") or {}
    if sender.get("login") == BOT_LOGIN:
        return 0
    issue_number = event["issue"]["number"]
    for pull in _related_pull_requests(client, issue_number):
        if pull["state"] == "open":
            client.set_commit_status(pull["head"]["sha"], "failure", "治理检查失败")
    client.comment(
        issue_number,
        "治理门禁拒绝：状态标签只能由治理工作流更新；已失败关闭当前治理检查。\n"
        f"{_audit_marker('invalid-status-label-change')}",
    )
    return 1


def _handle_closed_pull_request(event: dict[str, Any], client: GitHubClient) -> int:
    pull = event["pull_request"]
    if pull.get("merged") is not True:
        return 0
    head_sha = (pull.get("head") or {}).get("sha")
    merge_commit_sha = pull.get("merge_commit_sha")
    if not isinstance(head_sha, str) or not head_sha:
        return 1
    if not isinstance(merge_commit_sha, str) or not merge_commit_sha.strip():
        return 1
    issue_number = extract_linked_issue(pull.get("body") or "")
    if issue_number is None:
        return 0
    issue = client.issue(issue_number)
    if status_from_labels(_label_names(issue)) != "ACCEPTED":
        return 1
    if not _verification_passed(client, issue_number, pull):
        return 1
    related_pulls = _related_pull_requests(client, issue_number)
    if any(
        related.get("number") != pull.get("number") and related.get("state") == "open"
        for related in related_pulls
    ):
        return 1
    client.comment(issue_number, _closed_pull_request_audit(pull))
    client.update_issue(
        issue_number,
        labels=_replace_status_label(issue, "CLOSED"),
        state="closed",
    )
    return 0


def handle_pull_request(event: dict[str, Any], client: GitHubClient) -> int:
    if event.get("action") == "closed":
        return _handle_closed_pull_request(event, client)
    pull = event["pull_request"]
    issue_number = extract_linked_issue(pull.get("body") or "")
    if issue_number is None:
        context = PullRequestContext(
            body=pull.get("body") or "",
            draft=bool(pull.get("draft")),
            changed_files=client.pull_request_files(pull["number"]),
        )
        errors = validate_pull_request(context)
        if errors:
            client.set_commit_status(pull["head"]["sha"], "failure", "治理检查失败")
            print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
            return 1
        client.set_commit_status(pull["head"]["sha"], "success", "治理检查通过")
        print("governance: PASS")
        return 0
    issue = client.issue(issue_number)
    return _recompute_pull_request_status(client, issue, pull)


def _load_event(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate GitHub task governance.")
    parser.add_argument(
        "command",
        choices=(
            "issue-opened",
            "issue-closed",
            "transition",
            "verify",
            "pull-request",
            "recompute",
            "label-change",
        ),
    )
    parser.add_argument("--event", default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    args = parser.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN")
    if not args.event or not args.repository or not token:
        parser.error("--event, --repository and GITHUB_TOKEN are required")
    event = _load_event(args.event)
    client = GitHubClient(args.repository, token)
    handlers = {
        "issue-opened": handle_issue_opened,
        "issue-closed": handle_issue_closed,
        "transition": handle_transition,
        "verify": handle_verification,
        "pull-request": handle_pull_request,
        "recompute": lambda event, client: _recompute_issue_governance(
            event["issue"]["number"], client
        ),
        "label-change": handle_issue_label_change,
    }
    return handlers[args.command](event, client)


if __name__ == "__main__":
    raise SystemExit(main())
