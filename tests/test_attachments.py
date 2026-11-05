from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from types import SimpleNamespace

from autocoder.attachments import (
    _SafeRedirectHandler,
    allowed_attachment_hosts_for_repo_host,
    download_attachments,
    extract_urls,
    is_allowed_attachment_url,
)
from autocoder.gh import IssueComment, IssueDetail
from autocoder.run import _sync_issue_author_attachments


def test_extract_urls_dedup_and_trim() -> None:
    text = "see https://example.com/a.png). and https://example.com/a.png plus https://example.com/b."
    assert extract_urls(text) == ["https://example.com/a.png", "https://example.com/b"]


def test_extract_urls_empty() -> None:
    assert extract_urls("") == []
    assert extract_urls("no urls here") == []


def test_allowed_attachment_hosts_for_repo_host() -> None:
    hosts = allowed_attachment_hosts_for_repo_host("github.com")
    assert "github.com" in hosts
    assert "objects.githubusercontent.com" in hosts

    hosts2 = allowed_attachment_hosts_for_repo_host("ghe.example.com")
    assert hosts2 == {"ghe.example.com"}


def test_is_allowed_attachment_url() -> None:
    allowed = {"github.com"}
    assert is_allowed_attachment_url("https://github.com/user-attachments/files/123/a.txt", allowed_hosts=allowed)
    assert not is_allowed_attachment_url("http://github.com/user-attachments/files/123/a.txt", allowed_hosts=allowed)
    assert not is_allowed_attachment_url("https://example.com/a.txt", allowed_hosts=allowed)


def test_download_attachments_skips_disallowed_without_network(tmp_path: Path) -> None:
    res = download_attachments(
        urls=["http://example.com/a.txt", "https://example.com/b.txt"],
        dest_dir=tmp_path,
        auth_token="token",
        auth_host="github.com",
        total_cap_bytes=1024,
        allowed_hosts={"github.com"},
    )
    assert res.downloaded == ()
    assert res.skipped_urls == ("http://example.com/a.txt", "https://example.com/b.txt")


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self._read = False
        self.headers: dict[str, str] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if self._read:
            return b""
        self._read = True
        return self._body


class _Opener:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self._responses = responses

    def open(self, request: urllib.request.Request, *, timeout: float) -> _Response:
        return _Response(self._responses[request.full_url])


def test_redirect_handler_requires_https_and_strips_cross_host_auth() -> None:
    handler = _SafeRedirectHandler(allowed_hosts={"github.com", "objects.githubusercontent.com"})
    request = urllib.request.Request(
        "https://github.com/source",
        headers={"Authorization": "token example"},
    )

    assert (
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "http://github.com/insecure",
        )
        is None
    )

    cross_host = handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://objects.githubusercontent.com/file",
    )
    assert cross_host is not None
    assert cross_host.get_header("Authorization") is None

    same_host = handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://github.com/destination",
    )
    assert same_host is not None
    assert same_host.get_header("Authorization") == "token example"


def test_download_attachments_uses_distinct_names_and_removes_empty_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first_url = "https://github.com/user-attachments/files/one/shared.txt"
    second_url = "https://github.com/user-attachments/files/two/shared.txt"
    empty_url = "https://github.com/user-attachments/files/empty.txt"
    opener = _Opener(
        {
            first_url: b"first",
            second_url: b"second",
            empty_url: b"",
        }
    )
    monkeypatch.setattr("autocoder.attachments.urllib.request.build_opener", lambda handler: opener)

    result = download_attachments(
        urls=[first_url, second_url, empty_url],
        dest_dir=tmp_path,
        auth_token=None,
        total_cap_bytes=1024,
        allowed_hosts={"github.com"},
    )

    assert len(result.downloaded) == 2
    assert result.downloaded[0].path != result.downloaded[1].path
    assert {item.path.read_bytes() for item in result.downloaded} == {b"first", b"second"}
    assert result.skipped_urls == (empty_url,)
    assert len(list(tmp_path.iterdir())) == 2


def test_download_attachments_removes_partial_file_when_cap_is_exceeded(
    tmp_path: Path,
    monkeypatch,
) -> None:
    url = "https://github.com/user-attachments/files/large.txt"
    opener = _Opener({url: b"larger than cap"})
    monkeypatch.setattr("autocoder.attachments.urllib.request.build_opener", lambda handler: opener)

    result = download_attachments(
        urls=[url],
        dest_dir=tmp_path,
        auth_token=None,
        total_cap_bytes=4,
        allowed_hosts={"github.com"},
    )

    assert result.downloaded == ()
    assert result.skipped_urls == (url,)
    assert list(tmp_path.iterdir()) == []


def test_attachment_sync_applies_cap_to_existing_files(tmp_path: Path, monkeypatch) -> None:
    old_url = "https://github.com/old.txt"
    new_url = "https://github.com/new.txt"
    worktree = tmp_path / "worktree"
    artifacts = worktree / ".autocoder" / "artifacts"
    artifacts.mkdir(parents=True)
    existing = artifacts / "existing.txt"
    existing.write_bytes(b"1234")
    manifest_path = artifacts / "attachments-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "downloaded": [
                    {
                        "url": old_url,
                        "path": ".autocoder/artifacts/existing.txt",
                        "size_bytes": 4,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    issue = IssueDetail(
        number=1,
        title="attachments",
        url="https://github.com/owner/repo/issues/1",
        state="OPEN",
        updated_at="2026-01-01T00:00:00Z",
        author="trusted-user",
        body="",
        labels=("autocoder",),
        comments=(
            IssueComment(
                id="1",
                author="trusted-user",
                body=f"{old_url}\n{new_url}",
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
                url="",
            ),
        ),
    )
    runtime = SimpleNamespace(
        cfg=SimpleNamespace(allowed_github_logins=("trusted-user",)),
        repo=SimpleNamespace(host="github.com"),
    )
    monkeypatch.setattr("autocoder.run._ATTACHMENT_TOTAL_CAP_BYTES", 4)

    def unexpected_download(**kwargs):
        raise AssertionError("download should not run when existing files consume the cap")

    monkeypatch.setattr("autocoder.run.download_attachments", unexpected_download)

    _sync_issue_author_attachments(
        rt=runtime,
        issue=issue,
        pr=None,
        worktree_dir=worktree,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["downloaded"][0]["size_bytes"] == 4
    assert manifest["skipped_urls"] == [new_url]


def test_html_links_are_never_fetched(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError('not an attachment')
    monkeypatch.setattr(urllib.request, 'build_opener', no_network)
    result = download_attachments(urls=['https://github.com/o/r/issues/1'], dest_dir=tmp_path,
                                  auth_token='example', auth_host='github.com', total_cap_bytes=1024)
    assert not result.downloaded
    assert result.skipped_urls == ('https://github.com/o/r/issues/1',)


def test_modern_attachment_redirect_allowed_without_token():
    handler = _SafeRedirectHandler(allowed_hosts=allowed_attachment_hosts_for_repo_host('github.com'))
    req = urllib.request.Request('https://github.com/user-attachments/assets/example',
                                  headers={'Authorization': 'token example'})
    redirected = handler.redirect_request(req, None, 302, 'Found', {},
        'https://github-production-user-asset-6210df.s3.amazonaws.com/example')
    assert redirected is not None
    assert redirected.get_header('Authorization') is None


def test_redirect_only_hosts_and_cross_repo_raw_are_not_initial_urls():
    allowed = allowed_attachment_hosts_for_repo_host('github.com')
    for url in ('https://objects.githubusercontent.com/user-attachments/assets/example',
                'https://github-production-user-asset-6210df.s3.amazonaws.com/user-attachments/assets/example',
                'https://raw.githubusercontent.com/other/repo/main/file',
                'https://raw.githubusercontent.com/owner/repo/../../other/file',
                'https://github.com:bad/user-attachments/assets/example'):
        assert not is_allowed_attachment_url(url, allowed_hosts=allowed, repo_full_name='owner/repo')
    assert is_allowed_attachment_url('https://raw.githubusercontent.com/owner/repo/main/file',
                                     allowed_hosts=allowed, repo_full_name='owner/repo')
