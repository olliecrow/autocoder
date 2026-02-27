from __future__ import annotations

import argparse
import sys

from . import __version__
from .preflight import run_doctor, run_dry_run
from .run import run_session

_REPO_HELP = "repository SSH clone URL (example: git@github.com:owner/repo.git)"


def _completion_script(shell: str) -> str:
    if shell == "bash":
        return """# bash completion for autocoder
_autocoder_completion() {
  local cur prev words cword
  _init_completion || return
  local commands="run doctor dry-run completion help"
  if [[ ${cword} -eq 1 ]]; then
    COMPREPLY=( $(compgen -W "${commands}" -- "${cur}") )
    return
  fi
  case "${words[1]}" in
    completion)
      COMPREPLY=( $(compgen -W "bash zsh" -- "${cur}") )
      ;;
    run|doctor|dry-run)
      COMPREPLY=()
      ;;
    *)
      COMPREPLY=( $(compgen -W "${commands}" -- "${cur}") )
      ;;
  esac
}
complete -F _autocoder_completion autocoder
"""
    return """#compdef autocoder
_autocoder() {
  local -a commands
  commands=(
    'run:run autocoder for one repository'
    'doctor:run non-mutating preflight checks'
    'dry-run:print planned execution order without mutating state'
    'completion:print shell completion script'
    'help:show help text'
  )
  if (( CURRENT == 2 )); then
    _describe 'command' commands
    return
  fi
  case "${words[2]}" in
    completion)
      _values 'shell' bash zsh
      ;;
    *)
      _message 'repository SSH URL'
      ;;
  esac
}
_autocoder "$@"
"""


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="autocoder",
        description="Automate issue-to-pull-request execution for one repository at a time.",
        epilog=(
            "Examples:\n"
            "  autocoder run git@github.com:owner/repo.git\n"
            "  autocoder doctor git@github.com:owner/repo.git\n"
            "  autocoder dry-run git@github.com:owner/repo.git\n"
            "  autocoder completion zsh > ~/.zsh/completions/_autocoder"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser(
        "run",
        help="run autocoder for one repository",
        description="Run the issue polling and execution loop for one repository.",
    )
    run_p.add_argument("repo_ssh_url", help=_REPO_HELP)
    doctor_p = sub.add_parser(
        "doctor",
        help="run preflight checks",
        description="Run non-mutating preflight checks for one repository.",
    )
    doctor_p.add_argument("repo_ssh_url", help=_REPO_HELP)
    dry_run_p = sub.add_parser(
        "dry-run",
        help="show planned execution order",
        description="Print planned run order without mutating any repository state.",
    )
    dry_run_p.add_argument("repo_ssh_url", help=_REPO_HELP)
    completion_p = sub.add_parser(
        "completion",
        help="print shell completion script",
        description="Print shell completion script so tab completion can be installed.",
    )
    completion_p.add_argument("shell", choices=["bash", "zsh"], help="target shell")

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "run":
        return run_session(repo_ssh_url=args.repo_ssh_url)
    if args.cmd == "doctor":
        return run_doctor(repo_ssh_url=args.repo_ssh_url)
    if args.cmd == "dry-run":
        return run_dry_run(repo_ssh_url=args.repo_ssh_url)
    if args.cmd == "completion":
        print(_completion_script(args.shell), end="")
        return 0

    raise AssertionError(f"unhandled cmd: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
