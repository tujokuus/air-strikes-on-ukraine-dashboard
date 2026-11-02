"""Validate failure evidence without making GitHub or OpenAI API calls."""

import io
import json
from types import SimpleNamespace

import pytest

from monitoring.agent import collect_evidence
from monitoring.agent import analyze_failure


def monitor_run(**overrides):
    run = {
        "path": ".github/workflows/monitor.yml",
        "status": "completed",
        "conclusion": "failure",
        "event": "workflow_dispatch",
        "head_repository": {"full_name": "example/project"},
        "run_attempt": 2,
        "head_sha": "abc123",
    }
    run.update(overrides)
    return run


def test_evidence_is_bounded_and_redacted(monkeypatch):
    monkeypatch.setattr(collect_evidence, "gh", lambda *args: SimpleNamespace(stdout=json.dumps(monitor_run())))
    monkeypatch.setattr(collect_evidence.tempfile, "TemporaryFile", io.BytesIO)

    def fake_run(args, *, stdout, **kwargs):
        stdout.write(b"x" * 41000 + b"\ntoken=secret-value sk-example1234567890")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(collect_evidence.subprocess, "run", fake_run)
    evidence = collect_evidence.collect("123", "2", "example/project")

    assert evidence["attempt"] == "2"
    assert evidence["log_truncated"] is True
    assert len(evidence["failed_step_log"].encode()) <= collect_evidence.MAX_LOG_BYTES
    assert "secret-value" not in evidence["failed_step_log"]
    assert "sk-example1234567890" not in evidence["failed_step_log"]


@pytest.mark.parametrize("run", [
    monitor_run(conclusion="success"),
    monitor_run(path=".github/workflows/other.yml"),
    monitor_run(head_repository={"full_name": "other/project"}),
])
def test_only_failed_monitor_runs_are_accepted(monkeypatch, run):
    monkeypatch.setattr(collect_evidence, "gh", lambda *args: SimpleNamespace(stdout=json.dumps(run)))
    with pytest.raises(ValueError, match="not a completed failed monitor run"):
        collect_evidence.collect("123", None, "example/project")


def test_invalid_run_id_is_rejected():
    with pytest.raises(ValueError, match="positive integer"):
        collect_evidence.collect("123; unexpected", None, "example/project")


def test_missing_api_key_creates_failure_report(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert analyze_failure.main() == 1
    assert "OPENAI_API_KEY is missing" in capsys.readouterr().err
    assert "Analyysi ei valmistunut" in (tmp_path / "analysis-output" / "report.md").read_text(encoding="utf-8")
