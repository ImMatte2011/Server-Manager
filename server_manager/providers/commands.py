from __future__ import annotations

import subprocess
from dataclasses import dataclass

from server_manager.errors import ProviderCommandError


@dataclass(frozen=True)
class CommandOutput:
    stdout: str
    stderr: str
    returncode: int


def run_checked(argv: list[str], *, cwd: str | None = None, timeout: int = 60) -> CommandOutput:
    output = run_command(argv, cwd=cwd, timeout=timeout)
    if output.returncode != 0:
        raise ProviderCommandError(
            "Provider command failed.",
            details={"returncode": output.returncode},
        )
    return output


def run_command(argv: list[str], *, cwd: str | None = None, timeout: int = 60) -> CommandOutput:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            timeout=timeout,
            check=False,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise ProviderCommandError("Provider command is not available.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProviderCommandError("Provider command timed out.") from exc
    except OSError as exc:
        raise ProviderCommandError("Provider command could not be executed.") from exc

    output = CommandOutput(
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
        returncode=completed.returncode,
    )
    return output
