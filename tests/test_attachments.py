from __future__ import annotations

from pathlib import Path

from autocoder.attachments import allowed_attachment_hosts_for_repo_host, download_attachments, extract_urls, is_allowed_attachment_url


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
