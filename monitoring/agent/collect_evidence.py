"""Collect bounded, read-only evidence from one failed monitor run."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


MAX_LOG_BYTES = 40_000
WORKFLOW_PATH = ".github/workflows/monitor.yml"
OUTPUT_PATH = Path("analysis-output/evidence.json")


def gh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=True, timeout=90,
    )


def redact(text: str) -> str:
    """Remove common token formats and terminal escapes before analysis."""
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
    text = re.sub(r"(?i)\b(?:sk|ghp|github_pat|ghs|kgat)[-_][a-z0-9_-]{8,}\b", "[REDACTED]", text)
    text = re.sub(
        r"(?im)\b(authorization|api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]", text,
    )
    return text


def collect(run_id: str, attempt: str | None, repository: str) -> dict:
    if not re.fullmatch(r"[1-9][0-9]*", run_id):
        raise ValueError("Run ID must be a positive integer.")
    if attempt and not re.fullmatch(r"[1-9][0-9]*", attempt):
        raise ValueError("Run attempt must be a positive integer.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository name.")

    run = json.loads(gh("api", f"repos/{repository}/actions/runs/{run_id}").stdout)
    selected_attempt = attempt or str(run["run_attempt"])
    if attempt:
        run = json.loads(gh("api", f"repos/{repository}/actions/runs/{run_id}/attempts/{attempt}").stdout)
    if (
        run.get("path") != WORKFLOW_PATH
        or run.get("status") != "completed"
        or run.get("conclusion") != "failure"
        or run.get("event") not in {"schedule", "workflow_dispatch"}
        or (run.get("head_repository") or {}).get("full_name", "").lower() != repository.lower()
    ):
        raise ValueError("Selected run is not a completed failed monitor run from this repository.")

    # Stream to a temporary file instead of keeping potentially large logs in memory.
    warning = ""
    with tempfile.TemporaryFile() as output:
        try:
            result = subprocess.run(
                ["gh", "run", "view", run_id, "--repo", repository, "--attempt", selected_attempt, "--log-failed"],
                stdout=output, stderr=subprocess.DEVNULL, timeout=90, check=False,
            )
            if result.returncode:
                warning = "Failed-step logs could not be retrieved; only run metadata is available."
        except (OSError, subprocess.TimeoutExpired):
            warning = "Failed-step logs could not be retrieved; only run metadata is available."
        size = output.tell()
        output.seek(max(0, size - MAX_LOG_BYTES))
        log = output.read().decode("utf-8", errors="replace")
    if not log.strip():
        warning = warning or "No failed-step logs were available."
    return {
        "run_id": run_id,
        "attempt": selected_attempt,
        "run_url": f"https://github.com/{repository}/actions/runs/{run_id}/attempts/{selected_attempt}",
        "head_sha": run.get("head_sha", ""),
        "failed_step_log": redact(log),
        "log_truncated": size > MAX_LOG_BYTES,
        "limitations": [warning] if warning else [],
    }


def main() -> int:
    try:
        evidence = collect(os.environ.get("MONITOR_RUN_ID", ""), os.environ.get("MONITOR_RUN_ATTEMPT") or None, os.environ.get("GITHUB_REPOSITORY", ""))
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Collected evidence for failed monitor run {evidence['run_id']}, attempt {evidence['attempt']}.")
        if evidence["limitations"]:
            print(evidence["limitations"][0])
        return 0
    except ValueError as exc:
        print(f"Unable to collect or validate monitor run: {exc}", file=sys.stderr)
        return 1
    except (KeyError, json.JSONDecodeError, subprocess.SubprocessError, OSError) as exc:
        print(f"Unable to collect or validate monitor run: {type(exc).__name__}.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
