from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Iterable
import urllib.parse
import urllib.request


_URL_RE = re.compile(r"https?://[^\s<>\"]+")

_DEFAULT_ALLOWED_HOSTS_GITHUB_DOT_COM: set[str] = {
    # canonical
    "github.com",
    # common attachment/image hosts and redirect targets
    "objects.githubusercontent.com",
    "raw.githubusercontent.com",
    "user-images.githubusercontent.com",
    "media.githubusercontent.com",
}


def allowed_attachment_hosts_for_repo_host(repo_host: str) -> set[str]:
    """
    Return a conservative allowlist of hosts to auto-download from.

    Current policy: only auto-download from the repo host, plus GitHub-known attachment hosts
    when the repo host is `github.com`.
    """
    host = (repo_host or "").strip().lower()
    if not host:
        return set(_DEFAULT_ALLOWED_HOSTS_GITHUB_DOT_COM)
    if host == "github.com":
        return set(_DEFAULT_ALLOWED_HOSTS_GITHUB_DOT_COM)
    return {host}


def is_allowed_attachment_url(url: str, *, allowed_hosts: set[str]) -> bool:
    parsed = urllib.parse.urlparse(url or "")
    if parsed.scheme.lower() != "https":
        return False
    host = (parsed.hostname or "").lower()
    return bool(host) and host in {h.lower() for h in (allowed_hosts or set())}


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, *, allowed_hosts: set[str]):
        super().__init__()
        self._allowed_hosts = {h.lower() for h in (allowed_hosts or set())}

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is None:
            return None
        new_host = (urllib.parse.urlparse(new_req.full_url).hostname or "").lower()
        if not new_host or new_host not in self._allowed_hosts:
            # Block redirects to unexpected hosts.
            return None

        old_host = (urllib.parse.urlparse(req.full_url).hostname or "").lower()
        if old_host and new_host != old_host:
            # Don't forward auth headers cross-host (even within allowed hosts).
            new_req.headers.pop("Authorization", None)
            new_req.unredirected_hdrs.pop("Authorization", None)

        return new_req


@dataclass(frozen=True)
class DownloadedAttachment:
    url: str
    path: Path
    size_bytes: int


@dataclass(frozen=True)
class AttachmentDownloadResult:
    downloaded: tuple[DownloadedAttachment, ...]
    skipped_urls: tuple[str, ...]


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for raw in _URL_RE.findall(text or ""):
        # Trim common trailing punctuation from markdown formatting.
        u = raw.rstrip(").,;:]}>\"'")
        urls.append(u)

    # Stable de-dupe.
    out: list[str] = []
    seen: set[str] = set()
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _safe_filename(name: str) -> str:
    # Keep this conservative and portable.
    name = name.strip()
    if not name:
        return "attachment"
    out = []
    for ch in name:
        if ch.isalnum() or ch in ("-", "_", ".", "+"):
            out.append(ch)
        else:
            out.append("_")
    return "".join(out)[:200] or "attachment"


def download_attachments(
    *,
    urls: Iterable[str],
    dest_dir: Path,
    auth_token: str | None,
    auth_host: str | None = None,
    total_cap_bytes: int,
    allowed_hosts: set[str] | None = None,
    timeout_seconds: float = 60.0,
) -> AttachmentDownloadResult:
    dest_dir.mkdir(parents=True, exist_ok=True)
    allowed_hosts = set(allowed_hosts or _DEFAULT_ALLOWED_HOSTS_GITHUB_DOT_COM)
    opener = urllib.request.build_opener(_SafeRedirectHandler(allowed_hosts=allowed_hosts))
    auth_host = (auth_host or "").strip().lower()

    downloaded: list[DownloadedAttachment] = []
    skipped: list[str] = []
    used = 0

    for idx, url in enumerate(urls, start=1):
        if not is_allowed_attachment_url(url, allowed_hosts=allowed_hosts):
            skipped.append(url)
            continue

        if used >= total_cap_bytes:
            skipped.append(url)
            continue

        parsed = urllib.parse.urlparse(url)
        leaf = urllib.parse.unquote(Path(parsed.path).name)
        if not leaf:
            leaf = f"attachment-{idx}"
        filename = f"{idx:03d}-{_safe_filename(leaf)}"
        out_path = dest_dir / filename

        headers = {}
        # Only send auth to the repo host, plus GitHub-controlled attachment hosts on github.com.
        host = (parsed.hostname or "").lower()
        auth_ok = bool(auth_token and auth_host and host == auth_host)
        if auth_token and auth_host == "github.com" and host.endswith("githubusercontent.com"):
            auth_ok = True
        if auth_ok:
            headers["Authorization"] = f"token {auth_token}"

        req = urllib.request.Request(url, headers=headers)
        try:
            with opener.open(req, timeout=timeout_seconds) as resp:
                clen = resp.headers.get("Content-Length")
                if clen is not None:
                    try:
                        remaining = int(clen)
                    except ValueError:
                        remaining = None
                    else:
                        if used + remaining > total_cap_bytes:
                            skipped.append(url)
                            continue

                size = 0
                with out_path.open("wb") as f:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if used + size > total_cap_bytes:
                            # Cap exceeded: discard partial file.
                            f.close()
                            out_path.unlink(missing_ok=True)
                            size = 0
                            break
                        f.write(chunk)

                if size == 0:
                    skipped.append(url)
                    continue

                used += size
                downloaded.append(DownloadedAttachment(url=url, path=out_path, size_bytes=size))
        except Exception:
            # Treat attachment downloads as best-effort inputs; failures should not crash the session.
            # The calling layer can decide whether to ask the human for an alternative.
            out_path.unlink(missing_ok=True)
            skipped.append(url)
            continue

    return AttachmentDownloadResult(downloaded=tuple(downloaded), skipped_urls=tuple(skipped))
