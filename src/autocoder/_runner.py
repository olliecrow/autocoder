from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Mapping, Sequence


@dataclass(frozen=True)
class CmdResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


class CommandError(RuntimeError):
    def __init__(self, *, result: CmdResult):
        super().__init__(
            f"command failed (exit {result.returncode}): {result.args}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\n"
        )
        self.result = result


class CommandTimeout(RuntimeError):
    def __init__(
        self,
        *,
        argv: list[str],
        timeout_s: float,
        stdout: str = "",
        stderr: str = "",
    ):
        super().__init__(f"command timed out after {timeout_s}s: {argv}\nstdout:\n{stdout}\nstderr:\n{stderr}\n")
        # Do not assign to BaseException.args (which is used for the error message).
        self.argv = argv
        self.timeout_s = timeout_s
        self.stdout = stdout
        self.stderr = stderr


class Runner:
    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
        timeout_s: float | None = None,
        check: bool = True,
    ) -> CmdResult:
        raise NotImplementedError


class SubprocessRunner(Runner):
    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
        timeout_s: float | None = None,
        check: bool = True,
    ) -> CmdResult:
        argv = list(args)
        try:
            completed = subprocess.run(
                argv,
                cwd=str(cwd) if cwd else None,
                env={**os.environ, **env} if env else None,
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as e:
            def _coerce_timeout_text(val: str | bytes | None) -> str:
                if val is None:
                    return ""
                if isinstance(val, bytes):
                    return val.decode("utf-8", errors="replace")
                return val

            raise CommandTimeout(
                argv=argv,
                timeout_s=float(timeout_s or 0),
                stdout=_coerce_timeout_text(e.stdout),
                stderr=_coerce_timeout_text(e.stderr),
            ) from e
        res = CmdResult(
            args=argv,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if check and res.returncode != 0:
            raise CommandError(result=res)
        return res
