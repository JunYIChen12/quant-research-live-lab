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
ISSUE_CONTRACT_SECTIONS = ("目标", "范围", "不在范围", "验收标准", "风险与回滚")
PR_SECTIONS = ("变更", "证据", "风险与回滚", "未验证事项", "独立验收")

TRANSITIONS = {
    "": {"DRAFT"},
    "DRAFT": {"ANALYZING", "BLOCKED"},
    "ANALYZING": {"READY", "BLOCKED"},
    "READY": {"IN_PROGRESS", "BLOCKED"},
    "IN_PROGRESS": {"READY_FOR_VERIFY", "BLOCKED"},
    "READY_FOR_VERIFY": {"ACCEPTED", "REWORK", "BLOCKED"},
    "REWORK": {"IN_PROGRESS", "BLOCKED"},
    "BLOCKED": {"ANALYZING"},
    "ACCEPTED": {"CLOSED"},
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
    merged_pull_request: bool = False


@dataclass(frozen=True)
class PullRequestContext:
    body: str
    draft: bool
    changed_files: tuple[str, ...]
    linked_issue_number: int | None = None
    linked_issue_status: str | None = None


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
    if target not in TRANSITIONS.get(current, set()):
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
    elif target == "READY_FOR_VERIFY" and not context.open_pull_request:
        errors.append("READY_FOR_VERIFY 缺少关联 Pull Request")
    elif target == "ACCEPTED" and not context.independent_verification_passed:
        errors.append("ACCEPTED 缺少独立验收通过记录")
    elif target == "CLOSED":
        analysis_only = "type:analysis" in context.labels
        has_analysis_close = "关闭结论" in markdown_sections(context.body)
        if not context.merged_pull_request and not (analysis_only and has_analysis_close):
            errors.append("CLOSED 缺少已合并 Pull Request")
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
    allowed = {"IN_PROGRESS", "READY_FOR_VERIFY", "ACCEPTED"} if context.draft else {
        "READY_FOR_VERIFY",
        "ACCEPTED",
    }
    if status not in allowed:
        kind = "Draft" if context.draft else "非 Draft"
        expected = "IN_PROGRESS、READY_FOR_VERIFY 或 ACCEPTED" if context.draft else (
            "READY_FOR_VERIFY 或 ACCEPTED"
        )
        errors.append(f"{kind} Pull Request 要求关联 Issue 为 {expected}")
    return errors


def _is_small_documentation_change(files: tuple[str, ...]) -> bool:
    protected = (
        ".github/",
        "docs/governance/",
    )
    protected_files = {"AGENTS.md", "CONTRIBUTING.md", "SECURITY.md"}
    return bool(files) and all(
        path.endswith(".md")
        and (path.startswith("docs/") or path in {"README.md", "CHANGELOG.md"})
        and not path.startswith(protected)
        and path not in protected_files
        for path in files
    )


class GitHubClient:
    def __init__(self, repository: str, token: str) -> None:
        self.repository = repository
        self.token = token
        self.api_root = f"https://api.github.com/repos/{repository}"

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
        files = self.request("GET", f"/pulls/{number}/files?per_page=100")
        return tuple(item["filename"] for item in files)

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
    head_sha = pull["head"]["sha"].lower()
    trusted = {"OWNER", "MEMBER", "COLLABORATOR"}
    comment_passed = any(
        comment.get("author_association") in trusted
        and (comment.get("user") or {}).get("login") != pull["user"]["login"]
        and parse_verification_command(comment.get("body") or "") == head_sha
        for comment in client.issue_comments(issue_number)
    )
    review_passed = any(
        review["state"] == "APPROVED"
        and (review.get("commit_id") or "").lower() == head_sha
        and review["user"]["login"] != pull["user"]["login"]
        for review in client.pull_request_reviews(pull["number"])
    )
    return comment_passed or review_passed


def _transition_context(
    client: GitHubClient, issue: dict[str, Any], target_state: str
) -> TransitionContext:
    issue_number = issue["number"]
    pulls = _related_pull_requests(client, issue_number)
    open_pulls = [pull for pull in pulls if pull["state"] == "open"]
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
        merged_pull_request=any(pull.get("merged_at") for pull in pulls),
    )


def _replace_status_label(issue: dict[str, Any], target_state: str) -> list[str]:
    labels = [label for label in _label_names(issue) if not label.startswith(STATE_PREFIX)]
    labels.append(_status_label(target_state))
    return labels


def handle_issue_opened(event: dict[str, Any], client: GitHubClient) -> int:
    issue = event["issue"]
    if status_from_labels(_label_names(issue)):
        return 0
    client.update_issue(issue["number"], labels=_replace_status_label(issue, "DRAFT"))
    return 0


def handle_transition(event: dict[str, Any], client: GitHubClient) -> int:
    comment = event["comment"]
    target = parse_transition_command(comment.get("body") or "")
    if target is None:
        return 0
    if comment.get("author_association") not in {"OWNER", "MEMBER", "COLLABORATOR"}:
        client.comment(event["issue"]["number"], "治理门禁拒绝：只有仓库协作者可以改变状态。")
        return 1

    issue = client.issue(event["issue"]["number"])
    try:
        current = status_from_labels(_label_names(issue))
    except ValueError as exc:
        client.comment(issue["number"], f"治理门禁拒绝：{exc}")
        return 1
    errors = validate_transition(current, target, _transition_context(client, issue, target))
    if errors:
        client.comment(issue["number"], "治理门禁拒绝：\n- " + "\n- ".join(errors))
        return 1

    changes: dict[str, Any] = {"labels": _replace_status_label(issue, target)}
    if target == "CLOSED":
        changes["state"] = "closed"
    client.update_issue(issue["number"], **changes)
    open_pulls = [
        pull
        for pull in _related_pull_requests(client, issue["number"])
        if pull["state"] == "open"
    ]
    if target == "ACCEPTED":
        for pull in open_pulls:
            client.set_commit_status(pull["head"]["sha"], "success", "治理检查通过")
    elif target in {"IN_PROGRESS", "READY_FOR_VERIFY", "REWORK", "BLOCKED"}:
        for pull in open_pulls:
            client.set_commit_status(
                pull["head"]["sha"], "pending", f"任务状态为 {target}"
            )
    client.comment(issue["number"], f"治理门禁通过：`{current or 'NONE'}` → `{target}`。")
    return 0


def handle_verification(event: dict[str, Any], client: GitHubClient) -> int:
    comment = event["comment"]
    verified_sha = parse_verification_command(comment.get("body") or "")
    if verified_sha is None:
        return 0
    issue_number = event["issue"]["number"]
    if comment.get("author_association") not in {"OWNER", "MEMBER", "COLLABORATOR"}:
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
    if (comment.get("user") or {}).get("login") == pulls[0]["user"]["login"]:
        client.comment(issue_number, "治理门禁拒绝：实施者不能验收自己的 Pull Request。")
        return 1

    labels = [label for label in _label_names(issue) if label != "verification:passed"]
    labels.append("verification:passed")
    client.update_issue(issue_number, labels=labels)
    client.comment(issue_number, f"已记录当前 PR HEAD `{verified_sha}` 的独立验收通过。")
    return 0


def handle_issue_closed(event: dict[str, Any], client: GitHubClient) -> int:
    issue = client.issue(event["issue"]["number"])
    current = status_from_labels(_label_names(issue))
    if current == "CLOSED":
        return 0
    errors = validate_transition(current, "CLOSED", _transition_context(client, issue, "CLOSED"))
    if errors:
        client.update_issue(issue["number"], state="open")
        client.comment(issue["number"], "治理门禁重新打开 Issue：\n- " + "\n- ".join(errors))
        return 1
    client.update_issue(issue["number"], labels=_replace_status_label(issue, "CLOSED"))
    return 0


def handle_pull_request(event: dict[str, Any], client: GitHubClient) -> int:
    pull = event["pull_request"]
    issue_number = extract_linked_issue(pull.get("body") or "")
    issue_status = None
    if issue_number is not None:
        issue_status = status_from_labels(_label_names(client.issue(issue_number)))
    errors = validate_pull_request(
        PullRequestContext(
            body=pull.get("body") or "",
            draft=pull["draft"],
            changed_files=client.pull_request_files(pull["number"]),
            linked_issue_number=issue_number,
            linked_issue_status=issue_status,
        )
    )
    if errors:
        client.set_commit_status(pull["head"]["sha"], "failure", "治理检查失败")
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    verification_current = bool(
        issue_number is not None
        and issue_status == "ACCEPTED"
        and _verification_passed(client, issue_number, pull)
    )
    if issue_number is None or verification_current:
        client.set_commit_status(pull["head"]["sha"], "success", "治理检查通过")
        print("governance: PASS")
    else:
        description = (
            "等待当前提交的独立验收" if issue_status == "ACCEPTED" else "等待独立验收通过"
        )
        client.set_commit_status(pull["head"]["sha"], "pending", description)
        print("governance: PENDING independent verification")
    return 0


def _load_event(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate GitHub task governance.")
    parser.add_argument(
        "command",
        choices=("issue-opened", "issue-closed", "transition", "verify", "pull-request"),
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
    }
    return handlers[args.command](event, client)


if __name__ == "__main__":
    raise SystemExit(main())
