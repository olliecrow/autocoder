from __future__ import annotations

import argparse
import sys

from . import __version__
from .preflight import run_doctor, run_dry_run
from .run import run_session


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="autocoder")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="run autocoder for a single repo (polling loop)")
    run_p.add_argument("repo_ssh_url", help="repo SSH clone URL (e.g. git@github.com:org/repo.git)")
    doctor_p = sub.add_parser("doctor", help="run non-mutating preflight checks")
    doctor_p.add_argument("repo_ssh_url", help="repo SSH clone URL (e.g. git@github.com:org/repo.git)")
    dry_run_p = sub.add_parser("dry-run", help="show planned run order without mutating state")
    dry_run_p.add_argument("repo_ssh_url", help="repo SSH clone URL (e.g. git@github.com:org/repo.git)")

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "run":
        return run_session(repo_ssh_url=args.repo_ssh_url)
    if args.cmd == "doctor":
        return run_doctor(repo_ssh_url=args.repo_ssh_url)
    if args.cmd == "dry-run":
        return run_dry_run(repo_ssh_url=args.repo_ssh_url)

    raise AssertionError(f"unhandled cmd: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
