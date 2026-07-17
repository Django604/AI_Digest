from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

try:
    from .purge_jsdelivr_cache import build_dashboard_purge_paths, run_purge
except ImportError:
    from purge_jsdelivr_cache import build_dashboard_purge_paths, run_purge


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEADS_WORKBOOK = PROJECT_ROOT / "data" / "source" / "NEV+ICE_xsai.xlsm"
DEFAULT_ARRIVAL_WORKBOOK = PROJECT_ROOT / "data" / "source" / "NEV+ICE_ldai.xlsx"
DEFAULT_DASHBOARD_JSON = PROJECT_ROOT / "docs" / "data" / "dashboard.json"
DEFAULT_SUMMARY_JSON = PROJECT_ROOT / "docs" / "data" / "dashboard.summary.json"
DEFAULT_REBUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build_dashboard.py"
PUBLISH_TARGETS = (
    "data/source/NEV+ICE_xsai.xlsm",
    "data/source/NEV+ICE_ldai.xlsx",
    "docs/data/dashboard.json",
    "docs/data/dashboard.summary.json",
    "docs/data/monthly",
)
INTERRUPTED_EXIT_CODES = {3221225786, 130}
PUSH_TIMEOUT_SECONDS = 300
JSDELIVR_SETTLE_SECONDS = 15


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    output: str


class PublishError(RuntimeError):
    def __init__(
        self,
        phase: str,
        message: str,
        *,
        exit_code: int | None = None,
        command: str = "",
        output: str = "",
    ) -> None:
        super().__init__(message)
        self.phase = phase
        self.exit_code = exit_code
        self.command = command
        self.output = output


def resolve_publish_commit_message(*, business_date: str, mode: str, explicit_message: str) -> str:
    if explicit_message.strip():
        return explicit_message.strip()
    if business_date.strip():
        return f"Auto publish dashboard data {business_date} ({mode})"
    return f"Update dashboard data {time.strftime('%Y-%m-%d %H:%M:%S')}"


def _log_lines(log: Callable[[str], None] | None, prefix: str, output: str) -> None:
    if log is None:
        return
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if line:
            log(f"{prefix}{line}" if prefix else line)


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    log: Callable[[str], None] | None = None,
    prefix: str = "",
) -> CommandResult:
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    collected: list[str] = []
    for line in process.stdout:
        collected.append(line)
        text = line.rstrip("\r\n")
        if text and log is not None:
            log(f"{prefix}{text}" if prefix else text)
    exit_code = process.wait()
    return CommandResult(exit_code=exit_code, output="".join(collected))


def _run_command_with_timeout(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    log: Callable[[str], None] | None = None,
    prefix: str = "",
) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        timeout_message = f"Command timed out after {timeout_seconds} seconds: {_format_command(command)}"
        if output:
            timeout_message = f"{output.rstrip()}\n{timeout_message}"
        _log_lines(log, prefix, timeout_message)
        return CommandResult(exit_code=-1, output=timeout_message)

    _log_lines(log, prefix, completed.stdout or "")
    return CommandResult(exit_code=completed.returncode, output=completed.stdout or "")


def _format_command(command: list[str]) -> str:
    return " ".join(command)


def _raise_command_error(
    *,
    phase: str,
    command: list[str],
    result: CommandResult,
    retryable: bool = False,
) -> None:
    message = f"{phase} failed with exit code {result.exit_code}"
    details = result.output.strip()
    if details:
        message += f"\n{details}"
    if retryable:
        message += "\nThe push was interrupted once and retried, but the retry also failed."
    raise PublishError(
        phase,
        message,
        exit_code=result.exit_code,
        command=_format_command(command),
        output=details,
    )


def _run_git(
    args: list[str],
    *,
    cwd: Path,
    log: Callable[[str], None] | None = None,
) -> CommandResult:
    command = ["git", *args]
    result = _run_command(command, cwd=cwd, log=log)
    if result.exit_code != 0:
        _raise_command_error(phase="git", command=command, result=result)
    return result


def _run_build_dashboard(
    *,
    cwd: Path,
    log: Callable[[str], None] | None = None,
) -> None:
    command = [
        sys.executable,
        str(DEFAULT_REBUILD_SCRIPT),
        "--workbook",
        str(DEFAULT_LEADS_WORKBOOK),
        "--arrival-workbook",
        str(DEFAULT_ARRIVAL_WORKBOOK),
        "--out",
        str(DEFAULT_DASHBOARD_JSON),
        "--summary-out",
        str(DEFAULT_SUMMARY_JSON),
    ]
    result = _run_command(command, cwd=cwd, log=log)
    if result.exit_code != 0:
        _raise_command_error(
            phase="rebuild",
            command=command,
            result=result,
        )


def _ensure_git_available() -> None:
    if not shutil.which("git"):
        raise PublishError("precheck", "Git is not installed or not available in PATH.")


def _check_staged_files(repo_root: Path) -> None:
    staged = _run_git(["diff", "--cached", "--name-only"], cwd=repo_root).output
    staged_files = [line for line in staged.splitlines() if line.strip()]
    if not staged_files:
        return

    allowed = {item.lower() for item in PUBLISH_TARGETS}
    allowed_prefixes = tuple(f"{item.lower().rstrip('/')}/" for item in PUBLISH_TARGETS)
    unexpected = [
        item
        for item in staged_files
        if item.lower() not in allowed and not item.lower().startswith(allowed_prefixes)
    ]
    if unexpected:
        raise PublishError(
            "precheck",
            "There are already staged files outside the publish scope: "
            f"{', '.join(unexpected)}. Use allow_existing_staged only if you are sure.",
        )


def _retryable_push(result: CommandResult) -> bool:
    return result.exit_code in INTERRUPTED_EXIT_CODES


def _push_to_remote(*, repo_root: Path, remote: str, branch: str, log: Callable[[str], None]) -> None:
    push_command = ["git", "push", remote, f"HEAD:{branch}"]
    push_result = _run_command_with_timeout(
        push_command,
        cwd=repo_root,
        log=log,
        timeout_seconds=PUSH_TIMEOUT_SECONDS,
    )
    if push_result.exit_code != 0 and _retryable_push(push_result):
        log("Push was interrupted once; retrying after a short pause...")
        time.sleep(2)
        push_result = _run_command_with_timeout(
            push_command,
            cwd=repo_root,
            log=log,
            timeout_seconds=PUSH_TIMEOUT_SECONDS,
        )

    if push_result.exit_code != 0:
        _raise_command_error(
            phase="push",
            command=push_command,
            result=push_result,
            retryable=_retryable_push(push_result),
        )


def _resolve_github_repository(remote_url: str) -> str:
    normalized = remote_url.strip().rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    for marker in ("github.com:", "github.com/"):
        if marker not in normalized:
            continue
        repository = normalized.split(marker, 1)[1].strip("/")
        if len(repository.split("/")) == 2:
            owner, name = repository.split("/", 1)
            return f"{owner.lower()}/{name}"
    raise PublishError(
        "cache_purge",
        f"GitHub push succeeded, but the jsDelivr repository could not be inferred from remote URL: {remote_url}",
    )


def _purge_published_cache(
    *,
    repo_root: Path,
    remote_url: str,
    branch: str,
    log: Callable[[str], None],
) -> int:
    repository = _resolve_github_repository(remote_url)
    repo_paths = build_dashboard_purge_paths(repo_root / "docs")

    def purge_log(message: str) -> None:
        log(f"[jsDelivr] {message}")

    exit_code = run_purge(
        docs_dir=repo_root / "docs",
        repo_paths=repo_paths,
        repository=repository,
        ref=branch,
        log=purge_log,
    )
    if exit_code != 0:
        raise PublishError(
            "cache_purge",
            "GitHub push succeeded, but one or more critical jsDelivr cache entries failed to purge. "
            "Run the GitHub-only publish action again to retry cache refresh.",
        )
    return len(repo_paths)


def publish_dashboard(
    *,
    repo_root: Path | None = None,
    remote: str = "origin",
    branch: str = "main",
    commit_message: str = "",
    business_date: str = "",
    mode: str = "manual",
    skip_rebuild: bool = False,
    allow_existing_staged: bool = False,
    push_if_no_changes: bool = False,
    log: Callable[[str], None] | None = print,
) -> dict[str, str]:
    repo_root = PROJECT_ROOT if repo_root is None else repo_root
    _ensure_git_available()
    if not (repo_root / ".git").exists():
        raise PublishError(
            "precheck",
            "This folder is not a Git repository yet. Run 'git init' here or clone the GitHub repository first.",
        )

    _run_git(["rev-parse", "--show-toplevel"], cwd=repo_root)
    current_branch = _run_git(["branch", "--show-current"], cwd=repo_root).output.strip()
    if not current_branch:
        raise PublishError("precheck", "Current branch could not be determined. Please check out a branch before publishing.")

    remote_url = _run_git(["remote", "get-url", remote], cwd=repo_root).output.strip()
    if not remote_url:
        raise PublishError("precheck", f"Remote '{remote}' is not configured.")

    if not allow_existing_staged:
        _check_staged_files(repo_root)

    resolved_commit_message = resolve_publish_commit_message(
        business_date=business_date,
        mode=mode,
        explicit_message=commit_message,
    )

    log(f"Starting publish: remote={remote} branch={branch}")
    if skip_rebuild:
        log("Step 1/5: rebuild skipped by flag.")
    else:
        log("Step 1/5: rebuilding dashboard outputs...")
        _run_build_dashboard(cwd=repo_root, log=log)

    log("Step 2/5: staging dashboard publish files...")
    _run_git(["add", "--", *PUBLISH_TARGETS], cwd=repo_root, log=log)

    changed_output = _run_git(["diff", "--cached", "--name-only", "--", *PUBLISH_TARGETS], cwd=repo_root).output
    changed_targets = [line for line in changed_output.splitlines() if line.strip()]
    if not changed_targets:
        if push_if_no_changes:
            log(f"No publishable changes detected; checking pending commits on {remote}/{branch}...")
            _push_to_remote(repo_root=repo_root, remote=remote, branch=branch, log=log)
            log("GitHub push check completed successfully.")
            log(f"Waiting {JSDELIVR_SETTLE_SECONDS} seconds for the jsDelivr branch mirror...")
            time.sleep(JSDELIVR_SETTLE_SECONDS)
            log("Refreshing jsDelivr dashboard cache...")
            purged_file_count = _purge_published_cache(
                repo_root=repo_root,
                remote_url=remote_url,
                branch=branch,
                log=log,
            )
            log("jsDelivr dashboard cache refresh completed successfully.")
        else:
            log("No publishable changes detected. Nothing to commit.")
            purged_file_count = 0
        return {
            "publishStatus": "no_changes",
            "publishRemote": remote,
            "publishBranch": branch,
            "publishCommitMessage": resolved_commit_message,
            "publishCurrentBranch": current_branch,
            "publishRemoteUrl": remote_url,
            "publishPushAttempted": str(push_if_no_changes).lower(),
            "publishCachePurgeStatus": "success" if push_if_no_changes else "skipped",
            "publishCachePurgedFiles": str(purged_file_count),
        }

    log("Step 3/5: committing staged publish files...")
    _run_git(["commit", "-m", resolved_commit_message], cwd=repo_root, log=log)

    log(f"Step 4/5: pushing to {remote}/{branch}...")
    _push_to_remote(repo_root=repo_root, remote=remote, branch=branch, log=log)

    log(f"Waiting {JSDELIVR_SETTLE_SECONDS} seconds for the jsDelivr branch mirror...")
    time.sleep(JSDELIVR_SETTLE_SECONDS)
    log("Step 5/5: refreshing jsDelivr dashboard cache...")
    purged_file_count = _purge_published_cache(
        repo_root=repo_root,
        remote_url=remote_url,
        branch=branch,
        log=log,
    )

    log("")
    log("Dashboard publish completed successfully.")
    log(f"Remote: {remote}")
    log(f"Branch: {branch}")
    log(f"Current branch: {current_branch}")
    log(f"Remote URL: {remote_url}")
    log("Committed files:")
    for item in changed_targets:
        log(f"  - {item}")

    return {
        "publishStatus": "success",
        "publishRemote": remote,
        "publishBranch": branch,
        "publishCommitMessage": resolved_commit_message,
        "publishCurrentBranch": current_branch,
        "publishRemoteUrl": remote_url,
        "publishCachePurgeStatus": "success",
        "publishCachePurgedFiles": str(purged_file_count),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish dashboard data to GitHub.")
    parser.add_argument("--remote", default="origin", help="Git remote name used for publish.")
    parser.add_argument("--branch", default="main", help="Git branch name used for publish.")
    parser.add_argument("--commit-message", default="", help="Optional git commit message used for publish.")
    parser.add_argument("--business-date", default="", help="Business date used for the default auto publish commit message.")
    parser.add_argument("--mode", default="manual", help="Mode label used for the default auto publish commit message.")
    parser.add_argument("--skip-rebuild", action="store_true", help="Skip rebuilding dashboard outputs before publishing.")
    parser.add_argument(
        "--allow-existing-staged",
        action="store_true",
        help="Allow pre-existing staged files outside the publish scope.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        publish_dashboard(
            remote=args.remote,
            branch=args.branch,
            commit_message=args.commit_message,
            business_date=args.business_date,
            mode=args.mode,
            skip_rebuild=args.skip_rebuild,
            allow_existing_staged=args.allow_existing_staged,
        )
    except PublishError as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
