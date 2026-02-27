from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable

from ._runner import Runner


@dataclass(frozen=True)
class LabelDef:
    name: str
    color: str
    description: str


@dataclass(frozen=True)
class IssueSummary:
    number: int
    title: str
    url: str
    state: str
    updated_at: str
    labels: tuple[str, ...]
    author: str


@dataclass(frozen=True)
class IssueComment:
    id: str
    author: str
    body: str
    created_at: str
    updated_at: str
    url: str


@dataclass(frozen=True)
class IssueDetail:
    number: int
    title: str
    url: str
    state: str
    updated_at: str
    author: str
    body: str
    labels: tuple[str, ...]
    comments: tuple[IssueComment, ...]


@dataclass(frozen=True)
class PullRequestSummary:
    number: int
    title: str
    url: str
    state: str
    updated_at: str
    head_ref_name: str
    base_ref_name: str


@dataclass(frozen=True)
class PullRequestComment:
    id: str
    author: str
    body: str
    created_at: str
    updated_at: str
    url: str


@dataclass(frozen=True)
class PullRequestReview:
    id: str
    author: str
    body: str
    submitted_at: str
    state: str


@dataclass(frozen=True)
class PullRequestDetail:
    number: int
    title: str
    url: str
    state: str
    updated_at: str
    author: str
    head_ref_name: str
    base_ref_name: str
    is_cross_repository: bool
    merged_at: str | None
    body: str
    comments: tuple[PullRequestComment, ...]
    reviews: tuple[PullRequestReview, ...]


class GhClient:
    def __init__(self, *, runner: Runner, repo: str):
        self._runner = runner
        self._repo = repo

    @property
    def repo(self) -> str:
        return self._repo

    def _gh(
        self,
        args: list[str],
        *,
        input_text: str | None = None,
        check: bool = True,
    ) -> str:
        res = self._runner.run(
            ["gh", *args, "-R", self._repo],
            input_text=input_text,
            check=check,
        )
        return res.stdout

    def _gh_json(self, args: list[str], *, input_text: str | None = None) -> Any:
        out = self._gh(args, input_text=input_text)
        return json.loads(out)

    def repo_default_branch(self) -> str:
        # `gh repo view` does not support `-R/--repo`; the repository is a positional argument.
        res = self._runner.run(
            [
                "gh",
                "repo",
                "view",
                self._repo,
                "--json",
                "defaultBranchRef",
                "--jq",
                ".defaultBranchRef.name",
            ],
            check=True,
        )
        return res.stdout.strip()

    def ensure_labels(self, labels: Iterable[LabelDef]) -> None:
        for lab in labels:
            self._gh(
                [
                    "label",
                    "create",
                    lab.name,
                    "--color",
                    lab.color,
                    "--description",
                    lab.description,
                    "--force",
                ]
            )

    def list_open_issues(self, *, label: str, limit: int = 100) -> list[IssueSummary]:
        payload = self._gh_json(
            [
                "issue",
                "list",
                "--state",
                "open",
                "--limit",
                str(limit),
                "--label",
                label,
                "--json",
                "number,title,url,state,updatedAt,labels,author",
            ]
        )
        issues: list[IssueSummary] = []
        for it in payload:
            labels = tuple(sorted(lab["name"] for lab in (it.get("labels") or [])))
            issues.append(
                IssueSummary(
                    number=it["number"],
                    title=it["title"],
                    url=it["url"],
                    state=it["state"],
                    updated_at=it["updatedAt"],
                    labels=labels,
                    author=(it.get("author") or {}).get("login", ""),
                )
            )
        return issues

    def view_issue(self, *, number: int, include_comments: bool = True) -> IssueDetail:
        fields = [
            "number",
            "title",
            "url",
            "state",
            "updatedAt",
            "author",
            "body",
            "labels",
        ]
        if include_comments:
            fields.append("comments")

        it = self._gh_json(["issue", "view", str(number), "--json", ",".join(fields)])
        labels = tuple(sorted(lab["name"] for lab in (it.get("labels") or [])))

        comments: list[IssueComment] = []
        if include_comments:
            for c in (it.get("comments") or []):
                comments.append(
                    IssueComment(
                        id=c["id"],
                        author=(c.get("author") or {}).get("login", ""),
                        body=c.get("body") or "",
                        created_at=c.get("createdAt") or "",
                        updated_at=c.get("updatedAt") or "",
                        url=c.get("url") or "",
                    )
                )

        return IssueDetail(
            number=it["number"],
            title=it["title"],
            url=it["url"],
            state=it["state"],
            updated_at=it["updatedAt"],
            author=(it.get("author") or {}).get("login", ""),
            body=it.get("body") or "",
            labels=labels,
            comments=tuple(comments),
        )

    def issue_comment(self, *, number: int, body: str) -> None:
        # Pass the body via stdin to avoid putting large/multi-line content on the process command line.
        self._gh(["issue", "comment", str(number), "--body-file", "-"], input_text=body)

    def issue_add_labels(self, *, number: int, labels: Iterable[str]) -> None:
        for lab in labels:
            self._gh(["issue", "edit", str(number), "--add-label", lab])

    def issue_remove_labels(self, *, number: int, labels: Iterable[str]) -> None:
        for lab in labels:
            self._gh(["issue", "edit", str(number), "--remove-label", lab])

    def close_issue(self, *, number: int, comment: str | None = None) -> None:
        args = ["issue", "close", str(number)]
        if comment is not None:
            args.extend(["--comment", comment])
        self._gh(args)

    def list_prs(self, *, state: str = "open", head: str | None = None, limit: int = 50) -> list[PullRequestSummary]:
        args = [
            "pr",
            "list",
            "--state",
            state,
            "--limit",
            str(limit),
            "--json",
            "number,title,url,state,updatedAt,headRefName,baseRefName",
        ]
        if head:
            args.extend(["--head", head])
        payload = self._gh_json(args)
        prs: list[PullRequestSummary] = []
        for it in payload:
            prs.append(
                PullRequestSummary(
                    number=it["number"],
                    title=it["title"],
                    url=it["url"],
                    state=it["state"],
                    updated_at=it["updatedAt"],
                    head_ref_name=it["headRefName"],
                    base_ref_name=it["baseRefName"],
                )
            )
        return prs

    def search_open_prs_by_body_snippet(self, *, query: str, limit: int = 10) -> list[PullRequestSummary]:
        payload = self._gh_json(
            [
                "pr",
                "list",
                "--state",
                "open",
                "--limit",
                str(limit),
                "--search",
                query,
                "--json",
                "number,title,url,state,updatedAt,headRefName,baseRefName",
            ]
        )
        prs: list[PullRequestSummary] = []
        for it in payload:
            prs.append(
                PullRequestSummary(
                    number=it["number"],
                    title=it["title"],
                    url=it["url"],
                    state=it["state"],
                    updated_at=it["updatedAt"],
                    head_ref_name=it["headRefName"],
                    base_ref_name=it["baseRefName"],
                )
            )
        return prs

    def list_open_prs_closing_issue(self, *, issue_number: int, limit: int = 100) -> list[PullRequestSummary]:
        payload = self._gh_json(
            [
                "pr",
                "list",
                "--state",
                "open",
                "--limit",
                str(limit),
                "--json",
                "number,title,url,state,updatedAt,headRefName,baseRefName,closingIssuesReferences",
            ]
        )
        prs: list[PullRequestSummary] = []
        for it in payload:
            refs = it.get("closingIssuesReferences") or []
            closes_target = any((ref or {}).get("number") == issue_number for ref in refs)
            if not closes_target:
                continue
            prs.append(
                PullRequestSummary(
                    number=it["number"],
                    title=it["title"],
                    url=it["url"],
                    state=it["state"],
                    updated_at=it["updatedAt"],
                    head_ref_name=it["headRefName"],
                    base_ref_name=it["baseRefName"],
                )
            )
        return prs

    def view_pr(self, *, number: int, include_comments: bool = True) -> PullRequestDetail:
        return self._view_pr(number=number, include_comments=include_comments)

    def _view_pr(self, *, number: int, include_comments: bool) -> PullRequestDetail:
        fields = [
            "number",
            "title",
            "url",
            "state",
            "updatedAt",
            "author",
            "headRefName",
            "baseRefName",
            "isCrossRepository",
            "mergedAt",
            "body",
        ]
        if include_comments:
            fields.append("comments")
            fields.append("reviews")

        it = self._gh_json(["pr", "view", str(number), "--json", ",".join(fields)])

        comments: list[PullRequestComment] = []
        reviews: list[PullRequestReview] = []
        if include_comments:
            for c in (it.get("comments") or []):
                comments.append(
                    PullRequestComment(
                        id=c.get("id") or "",
                        author=(c.get("author") or {}).get("login", ""),
                        body=c.get("body") or "",
                        created_at=c.get("createdAt") or "",
                        updated_at=c.get("updatedAt") or "",
                        url=c.get("url") or "",
                    )
                )
            for r in (it.get("reviews") or []):
                reviews.append(
                    PullRequestReview(
                        id=r.get("id") or "",
                        author=(r.get("author") or {}).get("login", ""),
                        body=r.get("body") or "",
                        submitted_at=r.get("submittedAt") or "",
                        state=r.get("state") or "",
                    )
                )

        return PullRequestDetail(
            number=it["number"],
            title=it["title"],
            url=it["url"],
            state=it["state"],
            updated_at=it["updatedAt"],
            author=(it.get("author") or {}).get("login", ""),
            head_ref_name=it["headRefName"],
            base_ref_name=it["baseRefName"],
            is_cross_repository=bool(it.get("isCrossRepository")),
            merged_at=it.get("mergedAt"),
            body=it.get("body") or "",
            comments=tuple(comments),
            reviews=tuple(reviews),
        )

    def create_pr(self, *, title: str, body: str, base: str, head: str) -> PullRequestDetail:
        # `gh pr create` prints the created PR URL on success (no JSON mode).
        out = self._gh(
            [
                "pr",
                "create",
                "--title",
                title,
                "--body-file",
                "-",
                "--base",
                base,
                "--head",
                head,
            ],
            input_text=body,
        ).strip()

        pr_url = out.splitlines()[-1].strip()
        it = self._gh_json(
            [
                "pr",
                "view",
                pr_url,
                "--json",
                "number,title,url,state,updatedAt,author,headRefName,baseRefName,isCrossRepository,mergedAt,body",
            ]
        )
        return PullRequestDetail(
            number=it["number"],
            title=it["title"],
            url=it["url"],
            state=it["state"],
            updated_at=it["updatedAt"],
            author=(it.get("author") or {}).get("login", ""),
            head_ref_name=it["headRefName"],
            base_ref_name=it["baseRefName"],
            is_cross_repository=bool(it.get("isCrossRepository")),
            merged_at=it.get("mergedAt"),
            body=it.get("body") or "",
            comments=tuple(),
            reviews=tuple(),
        )

    def edit_pr(self, *, number: int, title: str | None = None, body: str | None = None) -> None:
        args = ["pr", "edit", str(number)]
        input_text = None
        if title is not None:
            args.extend(["--title", title])
        if body is not None:
            args.extend(["--body-file", "-"])
            input_text = body
        self._gh(args, input_text=input_text)

    def pr_comment(self, *, number: int, body: str) -> None:
        # Pass the body via stdin to avoid putting large/multi-line content on the process command line.
        self._gh(["pr", "comment", str(number), "--body-file", "-"], input_text=body)

    def close_pr(self, *, number: int, delete_branch: bool = False, comment: str | None = None) -> None:
        args = ["pr", "close", str(number)]
        if delete_branch:
            args.append("--delete-branch")
        if comment is not None:
            args.extend(["--comment", comment])
        self._gh(args)
