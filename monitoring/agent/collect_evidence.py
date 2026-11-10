"""Collect bounded, read-only evidence from one failed monitor run."""

from __future__ import annotations

import json
import os
import base64
from datetime import datetime
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile


MAX_LOG_BYTES = 40_000
MAX_ARTIFACT_BYTES = 5_000_000
MAX_IMAGE_BYTES = 5_000_000
MAX_IMAGE_PIXELS = 20_000_000
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


def fetch_screenshot(run_id: str, attempt_info: dict, repository: str) -> tuple[bytes | None, str]:
    """Fetch one screenshot only when its run attempt can be identified safely."""
    try:
        start = datetime.fromisoformat(attempt_info["run_started_at"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(attempt_info["updated_at"].replace("Z", "+00:00"))
        if start.tzinfo is None or end.tzinfo is None or end < start:
            raise ValueError("Invalid attempt timestamps")
        result = json.loads(gh("api", f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100").stdout)
        if result["total_count"] > 100:
            return None, "Screenshot unavailable: too many artifacts to select one reliably."
        candidates = []
        for artifact in result["artifacts"]:
            if artifact.get("name") != "dashboard-monitor-failure" or artifact.get("expired"):
                continue
            created = datetime.fromisoformat(artifact["created_at"].replace("Z", "+00:00"))
            if start <= created <= end:
                candidates.append(artifact)
        if len(candidates) != 1:
            return None, "No unique screenshot artifact was found for this attempt."
        artifact = candidates[0]
        artifact_id = str(artifact["id"])
        if not re.fullmatch(r"[1-9][0-9]*", artifact_id) or not 0 < artifact["size_in_bytes"] <= MAX_ARTIFACT_BYTES:
            return None, "The screenshot artifact is invalid or too large."
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(
                ["gh", "api", f"repos/{repository}/actions/artifacts/{artifact_id}/zip"],
                stdout=output, stderr=subprocess.DEVNULL, timeout=90, check=False,
            )
            if result.returncode or output.tell() > MAX_ARTIFACT_BYTES:
                return None, "The screenshot artifact download failed or was too large."
            output.seek(0)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                selected = next((name for name in ("failure-2.png", "failure-1.png") if names.count(name) == 1), None)
                if selected is None:
                    return None, "The artifact did not contain a usable screenshot."
                info = archive.getinfo(selected)
                if info.file_size > MAX_IMAGE_BYTES:
                    return None, "The screenshot was too large to analyze."
                with archive.open(info) as image_file:
                    image = image_file.read(MAX_IMAGE_BYTES + 1)
        if len(image) < 24 or len(image) > MAX_IMAGE_BYTES or image[:8] != b"\x89PNG\r\n\x1a\n" or image[12:16] != b"IHDR":
            return None, "The screenshot was not a valid PNG file."
        width = int.from_bytes(image[16:20], "big")
        height = int.from_bytes(image[20:24], "big")
        if not width or not height or width * height > MAX_IMAGE_PIXELS:
            return None, "The screenshot dimensions were invalid or too large."
        return image, f"One screenshot selected: {selected}."
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError, zipfile.BadZipFile):
        return None, "The screenshot could not be retrieved or verified; analysis uses logs only."


def collect(run_id: str, attempt: str | None, repository: str, *, data_release: bool = False) -> dict:
    if not re.fullmatch(r"[1-9][0-9]*", run_id):
        raise ValueError("Run ID must be a positive integer.")
    if attempt and not re.fullmatch(r"[1-9][0-9]*", attempt):
        raise ValueError("Run attempt must be a positive integer.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository name.")

    run = json.loads(gh("api", f"repos/{repository}/actions/runs/{run_id}").stdout)
    selected_attempt = attempt or str(run["run_attempt"])
    run = json.loads(gh("api", f"repos/{repository}/actions/runs/{run_id}/attempts/{selected_attempt}").stdout)
    if (
        run.get("path") != ('.github/workflows/data-release.yml' if data_release else WORKFLOW_PATH)
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
    if data_release:
        screenshot, screenshot_note = None, 'Data-release analysis uses failed-step logs only.'
    else:
        screenshot, screenshot_note = fetch_screenshot(run_id, run, repository)
    return {
        "run_id": run_id,
        "attempt": selected_attempt,
        "run_url": f"https://github.com/{repository}/actions/runs/{run_id}/attempts/{selected_attempt}",
        "head_sha": run.get("head_sha", ""),
        "failed_step_log": redact(log),
        "log_truncated": size > MAX_LOG_BYTES,
        "limitations": ([warning] if warning else []) + ([screenshot_note] if screenshot is None else []),
        "screenshot_note": screenshot_note,
        "screenshot_base64": base64.b64encode(screenshot).decode("ascii") if screenshot else None,
    }


def main() -> int:
    try:
        evidence = collect(os.environ.get("MONITOR_RUN_ID", ""), os.environ.get("MONITOR_RUN_ATTEMPT") or None, os.environ.get("GITHUB_REPOSITORY", ""), data_release=os.environ.get('EVIDENCE_KIND') == 'data_release')
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Collected evidence for failed monitor run {evidence['run_id']}, attempt {evidence['attempt']}.")
        print(evidence["screenshot_note"])
        for warning in evidence["limitations"]:
            if warning != evidence["screenshot_note"]:
                print(warning)
        return 0
    except ValueError as exc:
        print(f"Unable to collect or validate monitor run: {exc}", file=sys.stderr)
        return 1
    except (KeyError, json.JSONDecodeError, subprocess.SubprocessError, OSError) as exc:
        print(f"Unable to collect or validate monitor run: {type(exc).__name__}.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
