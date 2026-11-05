from __future__ import annotations

import os
import signal
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


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
        log_path: Path | None = None,
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
        log_path: Path | None = None,
    ) -> CmdResult:
        argv = list(args)
        if log_path is not None:
            return self._run_logged(argv=argv, cwd=cwd, env=env, input_text=input_text,
                                    timeout_s=timeout_s, check=check, log_path=log_path)
        try:
            completed = subprocess.run(
                argv,
                cwd=str(cwd) if cwd else None,
                env={**os.environ, **env} if env else None,
                input=input_text,
                text=True,
                capture_output=True,
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


    def _run_logged(self, *, argv, cwd, env, input_text, timeout_s, check, log_path):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as log, tempfile.TemporaryFile(mode="w+") as prompt:
            prompt.write(input_text or "")
            prompt.seek(0)
            proc = subprocess.Popen(argv, cwd=cwd, env={**os.environ, **env} if env else None,
                                    stdin=prompt, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
            try:
                returncode = proc.wait(timeout=timeout_s)
            except BaseException as exc:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
                finally:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    proc.wait()
                if isinstance(exc, subprocess.TimeoutExpired):
                    raise CommandTimeout(argv=argv, timeout_s=float(timeout_s or 0)) from exc
                raise
        result = CmdResult(args=argv, returncode=returncode, stdout="", stderr="")
        if check and returncode:
            raise CommandError(result=result)
        return result
